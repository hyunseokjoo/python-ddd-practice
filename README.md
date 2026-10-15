# Python DDD Practice

FastAPI·Pydantic v2·SQLAlchemy로 주문 도메인의 DDD, CQRS, Unit of Work를 연습한다.
`Order`가 업무 규칙을 담당하고, UoW가 주문과 항목을 함께 커밋하거나 롤백한다.
인증·권한 처리가 없는 학습용 예제다.

## 실행

Python 3.15.0, uv 0.13.1 이상, Docker Compose가 필요하다. 기본 DB는 PostgreSQL 17이다.

```bash
uv sync --locked
docker compose up -d --wait postgres
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:create_app --factory --reload
```

주문 생성·상품 추가·확정·취소·조회 API: [Swagger UI](http://127.0.0.1:8000/docs)

## DB 선택

설정을 바꾸려면 [.env.example](.env.example)을 `.env`로 복사하고 `DATABASE_URL`을 수정한다. 셸 환경변수가 `.env`보다 우선한다.

```dotenv
# PostgreSQL 17 (기본)
DATABASE_URL=postgresql+psycopg://orders:password@localhost:5432/orders
# MySQL 8.4 사용 시 위 값을 아래 값으로 교체
# DATABASE_URL=mysql+pymysql://orders:password@localhost:3306/orders?charset=utf8mb4
```

MySQL은 실행 명령의 `postgres`를 `mysql`로 바꾸고 마이그레이션부터 실행한다.
외부 MySQL도 로컬 설정과 같은 `utf8mb4_0900_bin` collation을 사용한다.
DB 전환 시 기존 데이터는 자동 이전되지 않는다.

## 구조

```text
src/app/
├── domains/orders/
│   ├── domain/          # 주문·값 객체·저장소 계약·업무 규칙
│   ├── application/     # Command·Query와 유스케이스 함수
│   ├── infrastructure/  # 저장소 구현, persistence/의 ORM 모델
│   ├── presentation/    # API·응답 스키마·예외 처리
│   └── container.py     # 주문 의존성 등록
├── shared/database/    # DB 연결·ORM 기반 클래스·UoW
├── bootstrap/          # 앱·요청별 컨테이너 조립·로그
└── main.py             # 앱 생성·수명 관리
```

요청마다 `Container.request_container()`로 `RequestContainer`를 만든다.
요청 컨테이너의 `session` 자원을 Repository와 UoW가 공유하며, 객체 조립은 컨테이너가 담당한다.
도메인별 컨테이너는 유스케이스에 Repository·UoW를 연결한다. API는 Command·Query를 전달해 유스케이스를 호출한다.
FastAPI의 `Depends`는 요청 컨테이너를 전달하고 요청 종료 시 자원을 정리하는 연결부 한 곳에서만 사용한다.

## 검사

| 테스트 경로 | 검증 대상 |
| --- | --- |
| `tests/unit/` | DB 없이 도메인·유스케이스·설정·로그 검증. Repository·UoW는 테스트 대역 사용 |
| `tests/integration/` | 실제 DB의 저장·롤백·동시성·마이그레이션, 앱 자원 수명 검증 |
| `tests/integration/api/` | TestClient와 실제 DB로 HTTP 계약·주문 흐름·의존성 연결 검증 |

API 테스트는 프로세스 내부 통합 테스트이며, 별도 서버·네트워크를 거치는 E2E는 아니다. 예외 핸들러 테스트는 DB 없이 HTTP 오류 매핑만 확인한다. DB fixture는 `integration/conftest.py`, 클라이언트 fixture는 `integration/api/conftest.py`에 한정한다.

단위 테스트는 DB 서버 없이 실행한다.

```bash
uv run --locked pytest tests/unit
```

DB가 실행 중이면 `uv run --locked pytest tests/integration`으로 통합 테스트만, `uv run --locked pytest tests/integration/api`로 API 테스트만 실행할 수 있다.

PostgreSQL을 실행한 상태에서:

```bash
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked alembic check
```

MySQL 테스트:

```bash
docker compose up -d --wait mysql
TEST_DATABASE_URL='mysql+pymysql://root:testpassword@localhost:3306/orders?charset=utf8mb4' uv run --locked pytest
```

테스트는 임시 스키마(PostgreSQL) 또는 DB(MySQL)를 만들고 삭제한다. 외부 테스트 서버는 `TEST_DATABASE_URL`로 지정하며, 계정에는 해당 공간 생성·삭제 및 테이블 관리 권한이 필요하다.
