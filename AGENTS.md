# 프로젝트 지침

Claude Code·Codex는 아래 스킬과 작업별 규칙을 읽고 적용한다.

## 필수 스킬

세션에서 첫 작업을 시작하기 전에 아래 세 파일을 모두 직접 읽고 적용한다. 이미 읽은 파일은 변경되지 않았다면 다시 읽지 않아도 된다. 이름이 같은 전역 스킬이 있어도 이 저장소의 경로를 기준으로 읽는다. 자동 선택이나 슬래시 명령 호출 여부에 의존하지 않는다.

| 스킬 원본 | 적용 범위 |
| --- | --- |
| [.agents/skills/i-have-adhd/SKILL.md](.agents/skills/i-have-adhd/SKILL.md) | 모든 사용자 응답 |
| [.agents/skills/ponytail/SKILL.md](.agents/skills/ponytail/SKILL.md) | 설계·구현·수정·검토, 기본 강도 `full` |
| [.agents/skills/karpathy-guidelines/SKILL.md](.agents/skills/karpathy-guidelines/SKILL.md) | 설계·구현·수정·검토 |

이 설정은 프로젝트 공통 기본값이다. 사용자가 명시적으로 끄거나 강도를 바꾸면 해당 요청을 따른다. 스킬을 읽을 수 없으면 적용했다고 주장하지 말고 누락된 경로를 알린다.

## 프로젝트 방향

Python과 FastAPI로 DDD(Domain-Driven Design)를 연습하는 프로젝트다. 데이터 모델과 입력 검증에는 Pydantic v2를 사용한다. 도메인 모델과 업무 규칙을 중심으로 개발하고, 구체적인 예제와 구조는 작업 요구사항에 맞춰 정한다.

응답 형식은 사용자 선호이며, 사용자의 ADHD 진단 여부를 추정하지 않는다.

## 상세 규칙 읽기

작업 시작 전에 해당하는 규칙 파일을 직접 읽고 적용한다. 여러 영역에 걸치면 관련 파일을 모두 읽는다.

| 작업 범위 | 읽을 규칙 |
| --- | --- |
| Python 코드·DDD 모델·테스트·설정·외부 계약·주석·로그 | [.agents/rules/coding.md](.agents/rules/coding.md) |
| 빌드·검사·컨테이너·문서 | [.agents/rules/operations.md](.agents/rules/operations.md) |
| 브랜치·커밋·푸시·PR/MR | [.agents/rules/git.md](.agents/rules/git.md) |
| 릴리스 노트·태그·릴리스 게시 | [.agents/rules/release.md](.agents/rules/release.md) |

공용 스킬은 `.agents/skills/`, 상세 규칙은 `.agents/rules/`의 원본에서 관리하고 도구별 사본을 만들지 않는다.
