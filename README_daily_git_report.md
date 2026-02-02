# 📋 Daily Git Report Generator

하루 동안의 Git 커밋을 분석하여 작업 내용과 **핵심 가치**를 정리해주는 Python 스크립트입니다.

## ✨ 주요 기능

- **다중 레포지토리 스캔**: 지정된 폴더 하위의 모든 Git 레포지토리를 자동 탐색
- **커밋 상세 분석**: 커밋 메시지, 변경 파일, 추가/삭제 라인 수 등 수집
- **AI 기반 핵심 가치 분석**: Claude API를 활용한 지능형 작업 분류 및 가치 도출
- **Markdown 리포트 생성**: 깔끔하게 정리된 일일 작업 보고서 자동 생성
- **작업 카테고리 분류**: feature, bugfix, refactor, docs 등 자동 분류

## 🚀 설치 방법

```bash
# 1. 스크립트 다운로드 후 의존성 설치
pip install -r requirements.txt

# 2. Anthropic API 키 설정 (선택사항 - AI 분석 사용 시)
export ANTHROPIC_API_KEY="your-api-key-here"
```

## 📖 사용법

### 기본 사용

```bash
# 현재 디렉토리 기준 오늘 커밋 분석
python daily_git_report.py -d .

# 특정 프로젝트 폴더 분석
python daily_git_report.py -d ~/projects

# 특정 날짜의 커밋 분석
python daily_git_report.py -d ~/projects --date 2024-01-15
```

### 고급 옵션

```bash
# 특정 작성자만 필터링
python daily_git_report.py -d ~/projects --author "홍길동"

# 특정 파일명으로 출력
python daily_git_report.py -d ~/projects -o my_report.md

# AI 분석 비활성화 (키워드 기반만 사용)
python daily_git_report.py -d ~/projects --no-ai

# API 키 직접 지정
python daily_git_report.py -d ~/projects --api-key "sk-ant-..."
```

### 전체 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-d, --directory` | 스캔할 기본 디렉토리 | 현재 디렉토리 |
| `-o, --output` | 출력 파일 경로 | `daily_report_YYYY-MM-DD.md` |
| `--date` | 대상 날짜 (YYYY-MM-DD) | 오늘 |
| `--author` | 특정 작성자만 필터링 | 전체 |
| `--no-ai` | AI 분석 비활성화 | False |
| `--api-key` | Anthropic API 키 | 환경변수 사용 |
| `-v, --verbose` | 상세 출력 모드 | False |

## 📊 출력 예시

생성되는 Markdown 리포트에는 다음 내용이 포함됩니다:

### 📌 오늘의 요약
오늘 작업의 전체적인 요약을 제공합니다.

### 💎 핵심 가치
- 코드 품질 개선
- 사용자 경험 향상
- 성능 최적화

### ✅ 주요 성과
커밋 메시지 기반 주요 성과 목록

### 📊 통계
| 항목 | 수치 |
|------|------|
| 레포지토리 | 3개 |
| 총 커밋 | 15개 |
| 변경된 파일 | 42개 |
| 추가된 라인 | +1,234 |
| 삭제된 라인 | -567 |

### 🏷️ 작업 카테고리
작업을 feature, bugfix, refactor, docs 등으로 자동 분류

### 📁 레포지토리별 상세
각 레포지토리와 커밋의 상세 정보

## 🔧 AI 분석 기능

### Claude API 사용 시
- 커밋 내용의 의미론적 분석
- 핵심 가치 자동 도출
- 작업의 비즈니스 영향도 평가
- 내일 이어할 작업 제안

### AI 없이 사용 시 (폴백 모드)
- 키워드 기반 카테고리 분류
- 기본적인 통계 분석
- 커밋 메시지 패턴 인식

## 📁 프로젝트 구조

```
daily_git_report/
├── daily_git_report.py    # 메인 스크립트
├── requirements.txt       # 의존성 목록
└── README.md             # 이 문서
```

## 🎯 활용 팁

### 1. 매일 자동 실행 (cron)
```bash
# 매일 오후 6시에 자동 실행
0 18 * * * cd ~/projects && python daily_git_report.py -d . -o ~/reports/$(date +\%Y-\%m-\%d).md
```

### 2. Git Alias 등록
```bash
git config --global alias.daily '!python ~/scripts/daily_git_report.py -d .'
# 사용: git daily
```

### 3. 팀 공유용
```bash
# 특정 작성자들만 필터링
python daily_git_report.py -d ~/team-project --author "팀원1|팀원2"
```

## 💡 핵심 가치 분류 기준

AI 분석 시 다음과 같은 핵심 가치들이 도출될 수 있습니다:

| 가치 | 설명 |
|------|------|
| 🚀 새로운 기능 개발 | 사용자에게 새로운 가치 제공 |
| 🐛 품질 개선 및 안정성 확보 | 버그 수정, 에러 처리 개선 |
| ♻️ 코드 품질 향상 | 리팩토링, 코드 정리 |
| 📝 문서화 및 지식 공유 | README, 주석, 문서 작성 |
| ⚡ 성능 최적화 | 속도 개선, 리소스 효율화 |
| 🔒 보안 강화 | 보안 취약점 수정 |
| 🧹 기술 부채 해소 | 레거시 코드 정리 |

## 📜 라이선스

MIT License

## 🤝 기여하기

버그 리포트나 기능 제안은 이슈로 등록해주세요!
