#!/usr/bin/env python3
"""
Daily Git Report Generator
===========================
하루의 git 커밋을 분석하여 작업 내용과 핵심 가치를 정리하는 스크립트

지원 AI 백엔드:
  - gemini: Google Gemini API (기본값)
  - anthropic: Anthropic API
  - claude-cli: Claude Code CLI (구독 토큰 사용)
  - keywords: AI 없이 키워드 기반 분석

사용법:
    python daily_git_report.py start              # 대화형 프로젝트 선택
    python daily_git_report.py add <경로> [이름]  # 프로젝트 추가
    python daily_git_report.py list               # 프로젝트 목록
    python daily_git_report.py remove <이름>      # 프로젝트 삭제
    python daily_git_report.py run -d <경로>      # 직접 실행
"""

import os
import subprocess
import json
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional
import re

# Optional imports for different AI backends
try:
    import google.generativeai as genai

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ============================================================
# 설정 파일 관리
# ============================================================


def get_git_user() -> Dict[str, str]:
    """현재 git 설정에서 사용자 정보 가져오기"""
    user_info = {"name": None, "email": None}

    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            user_info["name"] = result.stdout.strip()
    except:
        pass

    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            user_info["email"] = result.stdout.strip()
    except:
        pass

    return user_info


class ProjectConfig:
    """프로젝트 경로 설정을 관리하는 클래스"""

    DEFAULT_CONFIG_PATH = Path.home() / ".daily_git_report.json"

    def __init__(self, config_path: Path = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "projects": {},
            "default_backend": "gemini",
            "global_author": None,
            "use_git_user": True,
        }

    def _save_config(self):
        """설정 파일 저장"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def add_project(self, path: str, name: str = None, author: str = None) -> str:
        """프로젝트 추가"""
        path = str(Path(path).resolve())

        # 이름 자동 생성
        if not name:
            name = Path(path).name

        # 중복 이름 처리
        original_name = name
        counter = 1
        while name in self.config["projects"]:
            name = f"{original_name}_{counter}"
            counter += 1

        self.config["projects"][name] = {
            "path": path,
            "author": author,
            "added_at": datetime.now().isoformat(),
        }
        self._save_config()
        return name

    def remove_project(self, name: str) -> bool:
        """프로젝트 삭제"""
        if name in self.config["projects"]:
            del self.config["projects"][name]
            self._save_config()
            return True
        return False

    def update_project(
        self, name: str, path: str = None, author: str = None, new_name: str = None
    ) -> bool:
        """프로젝트 업데이트"""
        if name not in self.config["projects"]:
            return False

        project = self.config["projects"][name]

        if path:
            project["path"] = str(Path(path).resolve())
        if author is not None:
            project["author"] = author

        # 이름 변경
        if new_name and new_name != name:
            self.config["projects"][new_name] = project
            del self.config["projects"][name]

        self._save_config()
        return True

    def get_project(self, name: str) -> Optional[Dict]:
        """프로젝트 정보 가져오기"""
        return self.config["projects"].get(name)

    def list_projects(self) -> Dict[str, Dict]:
        """모든 프로젝트 목록"""
        return self.config["projects"]

    def set_default_backend(self, backend: str):
        """기본 백엔드 설정"""
        self.config["default_backend"] = backend
        self._save_config()

    def get_default_backend(self) -> str:
        """기본 백엔드 가져오기"""
        return self.config.get("default_backend", "gemini")

    def set_global_author(self, author: str):
        """전역 작성자 설정"""
        self.config["global_author"] = author
        self._save_config()

    def get_global_author(self) -> Optional[str]:
        """전역 작성자 가져오기"""
        return self.config.get("global_author")

    def set_use_git_user(self, use: bool):
        """git 사용자 자동 사용 설정"""
        self.config["use_git_user"] = use
        self._save_config()

    def get_use_git_user(self) -> bool:
        """git 사용자 자동 사용 여부"""
        return self.config.get("use_git_user", True)

    def get_effective_author(self, project_author: str = None) -> Optional[str]:
        """실제 사용할 작성자 결정 (우선순위: 프로젝트 > 전역 > git 설정)"""
        # 1. 프로젝트별 설정
        if project_author:
            return project_author

        # 2. 전역 설정
        global_author = self.get_global_author()
        if global_author:
            return global_author

        # 3. git 설정 자동 사용
        if self.get_use_git_user():
            git_user = get_git_user()
            return git_user.get("name") or git_user.get("email")

        return None


# ============================================================
# Git 관련 클래스
# ============================================================


class GitCommit:
    """Git 커밋 정보를 담는 클래스"""

    def __init__(
        self,
        hash: str,
        author: str,
        date: str,
        message: str,
        files_changed: List[str],
        stats: Dict,
        diff_summary: str = "",
    ):
        self.hash = hash
        self.author = author
        self.date = date
        self.message = message
        self.files_changed = files_changed
        self.stats = stats
        self.diff_summary = diff_summary

    def to_dict(self) -> Dict:
        return {
            "hash": self.hash,
            "author": self.author,
            "date": self.date,
            "message": self.message,
            "files_changed": self.files_changed,
            "stats": self.stats,
            "diff_summary": self.diff_summary,
        }


class RepoCommits:
    """레포지토리별 커밋 정보"""

    def __init__(self, repo_path: str, repo_name: str, commits: List[GitCommit]):
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.commits = commits
        self.remote_url = self._get_remote_url()

    def _get_remote_url(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git", "-C", self.repo_path, "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None

    def to_dict(self) -> Dict:
        return {
            "repo_path": self.repo_path,
            "repo_name": self.repo_name,
            "remote_url": self.remote_url,
            "commits": [c.to_dict() for c in self.commits],
        }


class GitRepoScanner:
    """Git 레포지토리를 스캔하고 커밋을 수집하는 클래스"""

    def __init__(self, base_path: str, target_date: date = None, author: str = None):
        self.base_path = Path(base_path).resolve()
        self.target_date = target_date or date.today()
        self.author = author

    def find_git_repos(self) -> List[Path]:
        """base_path 하위의 모든 git 레포지토리 찾기"""
        repos = []

        if (self.base_path / ".git").exists():
            repos.append(self.base_path)

        for depth in range(1, 4):
            pattern = "/".join(["*"] * depth) + "/.git"
            for git_dir in self.base_path.glob(pattern):
                repo_path = git_dir.parent
                if repo_path not in repos:
                    repos.append(repo_path)

        return repos

    def get_commits_for_date(self, repo_path: Path) -> List[GitCommit]:
        """특정 날짜의 커밋들을 가져오기"""
        commits = []

        date_str = self.target_date.strftime("%Y-%m-%d")
        since = f"{date_str} 00:00:00"
        until = f"{date_str} 23:59:59"

        cmd = [
            "git",
            "-C",
            str(repo_path),
            "log",
            f"--since={since}",
            f"--until={until}",
            "--format=%H|%an|%ai|%s",
            "--all",
        ]

        if self.author:
            cmd.extend(["--author", self.author])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return commits

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|", 3)
                if len(parts) < 4:
                    continue

                hash_val, author, date_val, message = parts
                files_changed = self._get_changed_files(repo_path, hash_val)
                stats = self._get_commit_stats(repo_path, hash_val)
                diff_summary = self._get_diff_summary(repo_path, hash_val)

                commits.append(
                    GitCommit(
                        hash=hash_val,
                        author=author,
                        date=date_val,
                        message=message,
                        files_changed=files_changed,
                        stats=stats,
                        diff_summary=diff_summary,
                    )
                )

        except subprocess.TimeoutExpired:
            print(f"  ⚠️ 타임아웃: {repo_path}")
        except Exception as e:
            print(f"  ⚠️ 에러: {repo_path} - {e}")

        return commits

    def _get_changed_files(self, repo_path: Path, commit_hash: str) -> List[str]:
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "show",
                    "--name-only",
                    "--format=",
                    commit_hash,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return [f for f in result.stdout.strip().split("\n") if f]
        except:
            return []

    def _get_commit_stats(self, repo_path: Path, commit_hash: str) -> Dict:
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "show",
                    "--stat",
                    "--format=",
                    commit_hash,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            lines = result.stdout.strip().split("\n")
            if lines:
                last_line = lines[-1]
                insertions = 0
                deletions = 0

                ins_match = re.search(r"(\d+) insertion", last_line)
                del_match = re.search(r"(\d+) deletion", last_line)

                if ins_match:
                    insertions = int(ins_match.group(1))
                if del_match:
                    deletions = int(del_match.group(1))

                return {"insertions": insertions, "deletions": deletions}
        except:
            pass
        return {"insertions": 0, "deletions": 0}

    def _get_diff_summary(
        self, repo_path: Path, commit_hash: str, max_chars: int = 4000
    ) -> str:
        """커밋의 실제 코드 변경 내용 (diff) 가져오기"""
        try:
            # 실제 diff 내용 가져오기 (코드 변경사항)
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "show",
                    "--format=",
                    "-p",
                    "--no-color",
                    commit_hash,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )

            diff_content = result.stdout.strip()

            # 너무 길면 잘라내기
            if len(diff_content) > max_chars:
                diff_content = diff_content[:max_chars] + "\n... (truncated)"

            return diff_content
        except:
            return ""

    def scan_all_repos(self) -> List[RepoCommits]:
        """모든 레포지토리 스캔"""
        repos = self.find_git_repos()
        all_repo_commits = []

        print(f"\n📁 스캔 대상: {self.base_path}")
        print(f"📅 대상 날짜: {self.target_date}")
        print(f"🔍 발견된 레포지토리: {len(repos)}개\n")

        for repo in repos:
            repo_name = repo.name
            print(f"  스캔 중: {repo_name}...", end=" ")

            commits = self.get_commits_for_date(repo)

            if commits:
                print(f"✅ {len(commits)}개 커밋 발견")
                all_repo_commits.append(
                    RepoCommits(
                        repo_path=str(repo), repo_name=repo_name, commits=commits
                    )
                )
            else:
                print("커밋 없음")

        return all_repo_commits


# ============================================================
# AI 분석
# ============================================================


class AIAnalyzer:
    """AI를 사용하여 커밋 내용을 분석하는 클래스"""

    ANALYSIS_PROMPT_TEMPLATE = """당신은 개발자의 일일 작업을 이력서/포트폴리오에 쓸 수 있도록 정리해주는 전문가입니다.

아래 Git 커밋들을 **레포지토리(프로젝트)별로 구분**해서 정리해주세요.

**절대 하지 말 것**:
- 커밋 메시지 그대로 복사 금지
- "feat:", "fix:" 같은 prefix 포함 금지
- Merge 커밋 무시

**반드시 할 것**:
- 레포지토리별로 성과를 분리해서 작성
- 파일 경로에서 도메인/모듈 파악
- 비즈니스 관점에서 가치 설명

JSON 형식:
```json
{
  "summary": "전체 요약 한 문장",
  "by_repo": {
    "레포지토리명1": {
      "achievements": ["성과1 - 상세설명", "성과2 - 상세설명"],
      "tech_stack": ["Kotlin", "Spring Boot"]
    },
    "레포지토리명2": {
      "achievements": ["성과1 - 상세설명"],
      "tech_stack": ["TypeScript", "React"]
    }
  },
  "impact_score": 8,
  "business_value": "비즈니스 임팩트 설명"
}
```

커밋 목록:
[COMMITS]

위 JSON 형식으로만 응답하세요."""

    def __init__(self, backend: str = "gemini", api_key: str = None):
        self.backend = backend
        self.api_key = api_key
        self._setup_backend()

    def _setup_backend(self):
        if self.backend == "gemini":
            if not HAS_GEMINI:
                print(
                    "  ⚠️ google-generativeai 패키지가 없습니다. 'pip install google-generativeai'로 설치하세요."
                )
                self.backend = "keywords"
                return

            key = (
                self.api_key
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
            )
            if not key:
                print(
                    "  ⚠️ Gemini API 키가 없습니다. GEMINI_API_KEY 환경변수를 설정하세요."
                )
                self.backend = "keywords"
                return

            genai.configure(api_key=key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")

        elif self.backend == "anthropic":
            if not HAS_ANTHROPIC:
                print(
                    "  ⚠️ anthropic 패키지가 없습니다. 'pip install anthropic'로 설치하세요."
                )
                self.backend = "keywords"
                return

            key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                print(
                    "  ⚠️ Anthropic API 키가 없습니다. ANTHROPIC_API_KEY 환경변수를 설정하세요."
                )
                self.backend = "keywords"
                return

            self.client = anthropic.Anthropic(api_key=key)

        elif self.backend == "claude-cli":
            try:
                result = subprocess.run(
                    ["claude", "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode != 0:
                    print("  ⚠️ Claude CLI를 찾을 수 없습니다.")
                    self.backend = "keywords"
            except Exception as e:
                print(f"  ⚠️ Claude CLI 확인 실패: {e}")
                self.backend = "keywords"

    def is_available(self) -> bool:
        return self.backend != "keywords"

    def get_backend_name(self) -> str:
        names = {
            "gemini": "Google Gemini",
            "anthropic": "Anthropic Claude API",
            "claude-cli": "Claude Code CLI (구독)",
            "keywords": "키워드 기반",
        }
        return names.get(self.backend, self.backend)

    def analyze_commits(self, repo_commits: List[RepoCommits]) -> Dict:
        if self.backend == "keywords":
            result = self._fallback_analysis(repo_commits)
            result["_ai_analyzed"] = False
            result["_ai_error"] = "키워드 기반 분석 사용"
            return result

        commits_text = self._format_commits_for_ai(repo_commits)
        prompt = self.ANALYSIS_PROMPT_TEMPLATE.replace("[COMMITS]", commits_text)

        try:
            if self.backend == "gemini":
                result = self._analyze_with_gemini(prompt)
            elif self.backend == "anthropic":
                result = self._analyze_with_anthropic(prompt)
            elif self.backend == "claude-cli":
                result = self._analyze_with_claude_cli(prompt)
            else:
                raise ValueError(f"알 수 없는 백엔드: {self.backend}")

            result["_ai_analyzed"] = True
            return result

        except Exception as e:
            error_msg = str(e)
            print(f"\n  ❌ AI 분석 실패: {error_msg}")
            print(f"  → 키워드 기반 분석으로 대체합니다.")

            result = self._fallback_analysis(repo_commits)
            result["_ai_analyzed"] = False
            result["_ai_error"] = error_msg
            return result

    def _analyze_with_gemini(self, prompt: str) -> Dict:
        response = self.model.generate_content(prompt)
        response_text = response.text

        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("JSON 응답을 파싱할 수 없습니다")

    def _analyze_with_anthropic(self, prompt: str) -> Dict:
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text

        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("JSON 응답을 파싱할 수 없습니다")

    def _analyze_with_claude_cli(self, prompt: str) -> Dict:
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                raise ValueError(f"Claude CLI 에러: {result.stderr}")

            response_text = result.stdout

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError("JSON 응답을 파싱할 수 없습니다")

        except subprocess.TimeoutExpired:
            raise ValueError("Claude CLI 타임아웃")

    def _format_commits_for_ai(self, repo_commits: List[RepoCommits]) -> str:
        lines = []

        for repo in repo_commits:
            lines.append(f"\n[{repo.repo_name}]")

            for commit in repo.commits:
                # 간결하게: 커밋 메시지 + 변경량 + 주요 파일
                files_str = ", ".join(commit.files_changed[:5])
                if len(commit.files_changed) > 5:
                    files_str += f" 외 {len(commit.files_changed) - 5}개"

                lines.append(
                    f"• {commit.message} (+{commit.stats['insertions']}/-{commit.stats['deletions']})"
                )
                lines.append(f"  파일: {files_str}")

        return "\n".join(lines)

    def _fallback_analysis(self, repo_commits: List[RepoCommits]) -> Dict:
        """AI 없이 파일 경로 기반 분석 (폴백) - 이력서용"""
        all_commits = []
        total_insertions = 0
        total_deletions = 0

        # 도메인/모듈별 변경 추적
        domain_changes = {}  # domain -> {"files": [], "insertions": 0, "deletions": 0}
        tech_stack = set()

        for repo in repo_commits:
            for commit in repo.commits:
                # Merge 커밋 제외
                if commit.message.lower().startswith("merge"):
                    continue

                all_commits.append(commit)
                total_insertions += commit.stats["insertions"]
                total_deletions += commit.stats["deletions"]

                for f in commit.files_changed:
                    # 기술 스택 추출
                    if f.endswith(".kt"):
                        tech_stack.add("Kotlin")
                    elif f.endswith(".java"):
                        tech_stack.add("Java")
                    elif f.endswith(".ts") or f.endswith(".tsx"):
                        tech_stack.add("TypeScript")
                    elif f.endswith(".py"):
                        tech_stack.add("Python")

                    if "spring" in f.lower() or "boot" in f.lower():
                        tech_stack.add("Spring Boot")
                    if "test" in f.lower():
                        tech_stack.add("테스트 코드")

                    # 도메인 추출 (파일 경로에서)
                    parts = f.lower().split("/")
                    for part in parts:
                        # 일반적인 도메인 키워드
                        domain_keywords = [
                            "user",
                            "order",
                            "product",
                            "payment",
                            "auth",
                            "consultation",
                            "category",
                            "admin",
                            "api",
                            "dashboard",
                            "fittem",
                            "diagnosis",
                            "ga",
                            "analytics",
                        ]
                        for kw in domain_keywords:
                            if kw in part:
                                domain = kw
                                if domain not in domain_changes:
                                    domain_changes[domain] = {
                                        "commits": [],
                                        "insertions": 0,
                                        "deletions": 0,
                                    }
                                domain_changes[domain]["commits"].append(commit.message)
                                domain_changes[domain]["insertions"] += commit.stats[
                                    "insertions"
                                ]
                                domain_changes[domain]["deletions"] += commit.stats[
                                    "deletions"
                                ]
                                break

        # 주요 성과 생성 (도메인별로 정리)
        achievements = []
        domain_names = {
            "consultation": "상담",
            "category": "카테고리",
            "admin": "관리자",
            "user": "사용자",
            "order": "주문",
            "product": "상품",
            "payment": "결제",
            "fittem": "핏템",
            "diagnosis": "진단",
            "ga": "GA 분석",
            "analytics": "분석",
            "dashboard": "대시보드",
            "api": "API",
            "auth": "인증",
        }

        for domain, data in sorted(
            domain_changes.items(), key=lambda x: x[1]["insertions"], reverse=True
        )[:5]:
            domain_kr = domain_names.get(domain, domain)
            achievements.append(
                f"{domain_kr} 기능 개선/구현 (+{data['insertions']}/-{data['deletions']} lines)"
            )

        # 요약 생성
        top_domains = [domain_names.get(d, d) for d in list(domain_changes.keys())[:3]]
        summary = (
            f"{', '.join(top_domains)} 관련 작업 수행"
            if top_domains
            else "코드 변경 작업 수행"
        )

        return {
            "summary": summary,
            "key_achievements": achievements
            if achievements
            else ["상세 내역은 커밋 로그 참조"],
            "tech_stack": list(tech_stack)[:6],
            "tech_highlights": list(tech_stack)[:6],  # 호환성
            "impact_score": min(10, len(all_commits) + (total_insertions // 200)),
            "business_value": f"총 {len(all_commits)}개 커밋, {total_insertions}줄 추가",
            "tomorrow_suggestions": [],
        }


# ============================================================
# Markdown 리포트 생성
# ============================================================


class MarkdownReportGenerator:
    """Markdown 형식의 리포트를 생성하는 클래스"""

    def __init__(self, target_date: date, backend_name: str = ""):
        self.target_date = target_date
        self.backend_name = backend_name

    def generate(self, repo_commits: List[RepoCommits], analysis: Dict) -> str:
        lines = []

        date_str = self.target_date.strftime("%Y년 %m월 %d일")
        weekday = ["월", "화", "수", "목", "금", "토", "일"][self.target_date.weekday()]

        lines.append(f"# 📋 일일 작업 리포트")
        lines.append(f"**{date_str} ({weekday}요일)**\n")

        lines.append("## 📌 오늘의 요약\n")
        lines.append(analysis.get("summary", "작업 내용이 없습니다."))
        lines.append("")

        # 레포지토리별 성과 (by_repo 필드가 있는 경우)
        if analysis.get("by_repo"):
            for repo_name, repo_data in analysis["by_repo"].items():
                lines.append(f"## 📁 {repo_name}\n")

                if repo_data.get("achievements"):
                    for achievement in repo_data["achievements"]:
                        lines.append(f"- {achievement}")

                lines.append("")

        # 기존 key_achievements (by_repo가 없는 경우에만)
        elif analysis.get("key_achievements"):
            lines.append("## ✅ 주요 성과\n")
            for achievement in analysis["key_achievements"]:
                lines.append(f"- {achievement}")
            lines.append("")

        total_commits = sum(len(r.commits) for r in repo_commits)
        total_files = sum(len(c.files_changed) for r in repo_commits for c in r.commits)
        total_insertions = sum(
            c.stats["insertions"] for r in repo_commits for c in r.commits
        )
        total_deletions = sum(
            c.stats["deletions"] for r in repo_commits for c in r.commits
        )

        lines.append("## 📊 통계\n")
        lines.append(f"| 항목 | 수치 |")
        lines.append(f"|------|------|")
        lines.append(f"| 레포지토리 | {len(repo_commits)}개 |")
        lines.append(f"| 총 커밋 | {total_commits}개 |")
        lines.append(f"| 변경된 파일 | {total_files}개 |")
        lines.append(f"| 추가된 라인 | +{total_insertions} |")
        lines.append(f"| 삭제된 라인 | -{total_deletions} |")

        if analysis.get("impact_score"):
            lines.append(f"| 영향도 점수 | {analysis['impact_score']}/10 |")
        lines.append("")

        if analysis.get("tomorrow_suggestions"):
            lines.append("## 📅 내일 제안 작업\n")
            for suggestion in analysis["tomorrow_suggestions"]:
                lines.append(f"- [ ] {suggestion}")
            lines.append("")

        # 비즈니스 가치 (있으면)
        if analysis.get("business_value"):
            lines.append("## 💼 비즈니스 임팩트\n")
            lines.append(analysis["business_value"])
            lines.append("")

        lines.append("---")
        generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # AI 분석 상태 표시
        ai_status = ""
        if analysis.get("_ai_analyzed") == False:
            ai_error = analysis.get("_ai_error", "알 수 없는 오류")
            ai_status = f" | ⚠️ AI 분석 실패: {ai_error}"

        lines.append(
            f"*Generated by Daily Git Report ({self.backend_name}) at {generated_time}{ai_status}*"
        )

        return "\n".join(lines)


# ============================================================
# CLI 명령어 핸들러
# ============================================================


def cmd_add(args):
    """프로젝트 추가"""
    config = ProjectConfig()

    path = args.path
    if not Path(path).exists():
        print(f"❌ 경로가 존재하지 않습니다: {path}")
        return 1

    name = config.add_project(path, args.name, args.author)
    print(f"✅ 프로젝트 추가됨: {name}")
    print(f"   경로: {Path(path).resolve()}")
    return 0


def cmd_list(args):
    """프로젝트 목록"""
    config = ProjectConfig()
    projects = config.list_projects()

    if not projects:
        print("📭 등록된 프로젝트가 없습니다.")
        print("   'daily_git_report.py add <경로>' 명령으로 프로젝트를 추가하세요.")
        return 0

    print("\n📁 등록된 프로젝트 목록")
    print("=" * 60)

    for i, (name, info) in enumerate(projects.items(), 1):
        path_exists = "✅" if Path(info["path"]).exists() else "❌"
        author_str = f" (author: {info['author']})" if info.get("author") else ""
        print(f"\n  [{i}] {name}{author_str}")
        print(f"      {path_exists} {info['path']}")

    print("\n" + "=" * 60)
    print(f"기본 백엔드: {config.get_default_backend()}")
    return 0


def cmd_remove(args):
    """프로젝트 삭제 (이름 또는 인덱스)"""
    config = ProjectConfig()
    projects = config.list_projects()

    # 인덱스로 입력된 경우 이름으로 변환
    name = args.name
    if name.isdigit():
        idx = int(name)
        project_names = list(projects.keys())
        if 1 <= idx <= len(project_names):
            name = project_names[idx - 1]
            print(f"📌 인덱스 [{idx}] → {name}")
        else:
            print(f"❌ 잘못된 인덱스: {idx} (1-{len(project_names)} 범위)")
            return 1

    if config.remove_project(name):
        print(f"✅ 프로젝트 삭제됨: {name}")
        return 0
    else:
        print(f"❌ 프로젝트를 찾을 수 없습니다: {name}")
        return 1


def cmd_update(args):
    """프로젝트 업데이트"""
    config = ProjectConfig()

    if config.update_project(args.name, args.path, args.author, args.new_name):
        print(f"✅ 프로젝트 업데이트됨: {args.new_name or args.name}")
        return 0
    else:
        print(f"❌ 프로젝트를 찾을 수 없습니다: {args.name}")
        return 1


def cmd_start(args):
    """대화형 프로젝트 선택 및 실행"""
    config = ProjectConfig()
    projects = config.list_projects()

    if not projects:
        print("📭 등록된 프로젝트가 없습니다.")
        print("   'daily_git_report.py add <경로>' 명령으로 프로젝트를 추가하세요.")
        return 0

    print("\n" + "=" * 60)
    print("📋 Daily Git Report Generator")
    print("=" * 60)
    print("\n📁 프로젝트 선택:\n")

    project_list = list(projects.items())

    for i, (name, info) in enumerate(project_list, 1):
        path_exists = "✅" if Path(info["path"]).exists() else "❌"
        author_str = f" ({info['author']})" if info.get("author") else ""
        print(f"  [{i}] {name}{author_str}")
        print(f"      {path_exists} {info['path']}")
        print()

    print(f"  [a] 모든 프로젝트")
    print(f"  [q] 종료")
    print()

    try:
        choice = input("선택 (번호 또는 a/q): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n취소됨")
        return 0

    if choice == "q":
        return 0

    # 선택된 프로젝트들
    selected_projects = []

    if choice == "a":
        selected_projects = project_list
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(project_list):
                selected_projects = [project_list[idx]]
            else:
                print("❌ 잘못된 선택입니다.")
                return 1
        except ValueError:
            print("❌ 잘못된 입력입니다.")
            return 1

    # 날짜 선택
    print(f"\n📅 날짜 선택 (기본값: 오늘 {date.today()}):")
    try:
        date_input = input("날짜 (YYYY-MM-DD, Enter=오늘): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n취소됨")
        return 0

    target_date = date.today()
    if date_input:
        try:
            target_date = datetime.strptime(date_input, "%Y-%m-%d").date()
        except ValueError:
            print("❌ 잘못된 날짜 형식입니다. 오늘 날짜로 진행합니다.")

    # 백엔드 선택
    default_backend = config.get_default_backend()
    print(f"\n🤖 AI 백엔드 선택 (기본값: {default_backend}):")
    print("  [1] gemini - Google Gemini API")
    print("  [2] anthropic - Anthropic Claude API")
    print("  [3] claude-cli - Claude Code CLI (구독)")
    print("  [4] keywords - AI 없이 키워드 기반")

    backend_map = {"1": "gemini", "2": "anthropic", "3": "claude-cli", "4": "keywords"}

    try:
        backend_input = input(f"선택 (1-4, Enter={default_backend}): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n취소됨")
        return 0

    backend = backend_map.get(backend_input, default_backend)

    # 실행
    print("\n" + "=" * 60)

    all_repo_commits = []

    for name, info in selected_projects:
        path = info["path"]
        project_author = info.get("author")

        # 실제 사용할 작성자 결정
        effective_author = config.get_effective_author(project_author)

        if not Path(path).exists():
            print(f"⚠️ 경로가 존재하지 않습니다: {path}")
            continue

        if effective_author:
            print(f"👤 작성자 필터: {effective_author}")

        scanner = GitRepoScanner(
            base_path=path, target_date=target_date, author=effective_author
        )

        repo_commits = scanner.scan_all_repos()
        all_repo_commits.extend(repo_commits)

    if not all_repo_commits:
        print(f"\n⚠️ {target_date}에 커밋이 없습니다.")
        return 0

    # AI 분석
    print("\n🤖 AI 분석 중...")
    analyzer = AIAnalyzer(backend=backend)
    print(f"   사용 백엔드: {analyzer.get_backend_name()}")

    analysis = analyzer.analyze_commits(all_repo_commits)

    # 리포트 생성
    print("\n📝 리포트 생성 중...")
    generator = MarkdownReportGenerator(target_date, analyzer.get_backend_name())
    report = generator.generate(all_repo_commits, analysis)

    # 파일 저장 (report 폴더에)
    output_path = f"report/daily_report_{target_date.strftime('%Y-%m-%d')}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ 리포트 생성 완료: {output_path}")

    # 요약 출력
    print("\n" + "=" * 60)
    print("📌 오늘의 핵심 가치:")
    for value in analysis.get("core_values", []):
        print(f"   💎 {value}")
    print("=" * 60)

    return 0


def cmd_run(args):
    """직접 실행 (기존 방식)"""
    target_date = date.today()
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ 잘못된 날짜 형식: {args.date}")
            return 1

    output_path = (
        args.output or f"report/daily_report_{target_date.strftime('%Y-%m-%d')}.md"
    )

    print("=" * 60)
    print("📋 Daily Git Report Generator")
    print("=" * 60)

    scanner = GitRepoScanner(
        base_path=args.directory, target_date=target_date, author=args.author
    )

    repo_commits = scanner.scan_all_repos()

    if not repo_commits:
        print(f"\n⚠️ {target_date}에 커밋이 없습니다.")
        return 0

    print("\n🤖 AI 분석 중...")
    analyzer = AIAnalyzer(backend=args.backend, api_key=args.api_key)
    print(f"   사용 백엔드: {analyzer.get_backend_name()}")

    analysis = analyzer.analyze_commits(repo_commits)

    print("\n📝 리포트 생성 중...")
    generator = MarkdownReportGenerator(target_date, analyzer.get_backend_name())
    report = generator.generate(repo_commits, analysis)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ 리포트 생성 완료: {output_path}")

    print("\n" + "=" * 60)
    print("📌 오늘의 핵심 가치:")
    for value in analysis.get("core_values", []):
        print(f"   💎 {value}")
    print("=" * 60)

    return 0


def cmd_config(args):
    """설정 관리"""
    config = ProjectConfig()

    if args.backend:
        config.set_default_backend(args.backend)
        print(f"✅ 기본 백엔드 설정됨: {args.backend}")

    if args.author:
        config.set_global_author(args.author)
        print(f"✅ 전역 작성자 설정됨: {args.author}")

    if args.use_git_user is not None:
        config.set_use_git_user(args.use_git_user)
        print(
            f"✅ Git 사용자 자동 사용: {'활성화' if args.use_git_user else '비활성화'}"
        )

    if args.clear_author:
        config.set_global_author(None)
        print(f"✅ 전역 작성자 설정 삭제됨")

    # 현재 git 사용자 정보
    git_user = get_git_user()

    print(f"\n⚙️ 현재 설정:")
    print(f"   설정 파일: {config.config_path}")
    print(f"   기본 백엔드: {config.get_default_backend()}")
    print(f"   등록된 프로젝트: {len(config.list_projects())}개")
    print(f"\n👤 작성자 설정:")
    print(f"   전역 작성자: {config.get_global_author() or '(없음)'}")
    print(f"   Git 사용자 자동 사용: {'예' if config.get_use_git_user() else '아니오'}")
    print(
        f"   현재 Git 사용자: {git_user.get('name') or '(없음)'} <{git_user.get('email') or '없음'}>"
    )
    print(f"   → 실제 적용될 작성자: {config.get_effective_author() or '(전체)'}")

    return 0


# ============================================================
# 메인
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="하루의 Git 커밋을 분석하여 작업 리포트를 생성합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # start 명령
    start_parser = subparsers.add_parser("start", help="대화형 프로젝트 선택 및 실행")
    start_parser.set_defaults(func=cmd_start)

    # add 명령
    add_parser = subparsers.add_parser("add", help="프로젝트 추가")
    add_parser.add_argument("path", help="프로젝트 경로")
    add_parser.add_argument("name", nargs="?", help="프로젝트 이름 (선택)")
    add_parser.add_argument("--author", help="기본 작성자 필터")
    add_parser.set_defaults(func=cmd_add)

    # list 명령
    list_parser = subparsers.add_parser("list", help="프로젝트 목록")
    list_parser.set_defaults(func=cmd_list)

    # remove 명령
    remove_parser = subparsers.add_parser("remove", help="프로젝트 삭제")
    remove_parser.add_argument("name", help="프로젝트 이름 또는 인덱스 번호")
    remove_parser.set_defaults(func=cmd_remove)

    # update 명령
    update_parser = subparsers.add_parser("update", help="프로젝트 업데이트")
    update_parser.add_argument("name", help="프로젝트 이름")
    update_parser.add_argument("--path", help="새 경로")
    update_parser.add_argument("--author", help="새 작성자 필터")
    update_parser.add_argument("--new-name", help="새 이름")
    update_parser.set_defaults(func=cmd_update)

    # run 명령 (직접 실행)
    run_parser = subparsers.add_parser("run", help="직접 실행")
    run_parser.add_argument("-d", "--directory", default=".", help="스캔할 디렉토리")
    run_parser.add_argument("-o", "--output", help="출력 파일 경로")
    run_parser.add_argument("--date", help="대상 날짜 (YYYY-MM-DD)")
    run_parser.add_argument("--author", help="작성자 필터")
    run_parser.add_argument(
        "-b",
        "--backend",
        choices=["gemini", "anthropic", "claude-cli", "keywords"],
        default="gemini",
        help="AI 백엔드",
    )
    run_parser.add_argument("--api-key", help="API 키")
    run_parser.set_defaults(func=cmd_run)

    # config 명령
    config_parser = subparsers.add_parser("config", help="설정 관리")
    config_parser.add_argument(
        "--backend",
        choices=["gemini", "anthropic", "claude-cli", "keywords"],
        help="기본 백엔드 설정",
    )
    config_parser.add_argument("--author", help="전역 작성자 설정 (내 커밋만 필터)")
    config_parser.add_argument(
        "--use-git-user",
        type=lambda x: x.lower() == "true",
        metavar="true/false",
        dest="use_git_user",
        help="Git 설정에서 사용자 자동 가져오기 (기본: true)",
    )
    config_parser.add_argument(
        "--clear-author", action="store_true", help="전역 작성자 설정 삭제"
    )
    config_parser.set_defaults(func=cmd_config, use_git_user=None)

    args = parser.parse_args()

    # 명령어가 없으면 start 실행
    if args.command is None:
        args.func = cmd_start
        return cmd_start(args)

    return args.func(args)


if __name__ == "__main__":
    exit(main())
