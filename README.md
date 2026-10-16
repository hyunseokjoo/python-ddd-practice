# Python DDD Practice

FastAPI·Pydantic v2·SQLAlchemy로 주문 도메인의 DDD, CQRS, 트랜잭션 전파를 연습한다.
`Order`가 업무 규칙을 담당하고, `sqlalchemy-transactional`이 주문과 항목을 함께 커밋하거나 롤백한다.
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
├── shared/database/    # DB 연결·ORM 기반 클래스
├── bootstrap/          # 앱·요청별 컨테이너 조립·로그
└── main.py             # 앱 생성·수명 관리
```

앱 `Container`는 비동기 엔진과 `async_sessionmaker`의 수명을 관리한다.
요청마다 `RequestContainer`를 만들고, `get_request_container()`가 라이브러리의
`sessionmaker_context()`에 앱의 세션 팩토리를 연결한다. FastAPI의 `Depends`는 이 경계 한 곳에만 둔다.
도메인 컨테이너가 Repository와 비동기 유스케이스 함수를 조립하며, API는 이를 `await`한다.

Repository는 세션을 보관하지 않고 각 메서드에서 `current_session()`을 사용한다.
따라서 `REQUIRES_NEW`에서도 해당 트랜잭션의 세션을 사용한다. 조회·변경 유스케이스 모두
`@transactional`을 사용하며, 라이브러리가 세션 생성·커밋·롤백·종료를 담당한다.
직접 작성한 UoW와 수동 `commit()`은 사용하지 않는다.

환경변수의 DB URL은 기존과 같다. PostgreSQL은 psycopg의 비동기 연결을 쓰며,
MySQL의 `mysql+pymysql` URL은 앱 안에서 `mysql+aiomysql`로 변환한다.
Alembic은 기존 동기 드라이버를 사용한다.

## 트랜잭션 전파

[`sqlalchemy-transactional` 1.0.3](https://pypi.org/project/sqlalchemy-transactional/1.0.3/)을 사용한다.

| 전파 정책 | 동작 |
| --- | --- |
| `REQUIRED` (기본) | 기존 트랜잭션에 참여하고, 없으면 새로 시작 |
| `REQUIRES_NEW` | 별도 세션에서 독립적으로 커밋·롤백한 후 바깥 세션 복원 |
| `NESTED` | 기존 트랜잭션 안에서는 SAVEPOINT 사용, 없으면 새 트랜잭션 시작 |
| `MANDATORY` | 기존 트랜잭션이 없으면 오류 |

여러 유스케이스를 원자적으로 실행하려면 상위 조율 함수에도 `@transactional`을 붙인다.
다음 함수는 요청의 `sessionmaker_context()` 안에서 호출한다.

```python
from sqlalchemy_transactional.asyncio import transactional


@transactional
async def create_two_orders(container, first_command, second_command):
    await container.orders().create_order(first_command)
    await container.orders().create_order(second_command)


# 두 호출이 성공하면 상위 함수가 종료될 때 함께 커밋한다.
```

CLI·배치에서는 `async with open_database(database_url) as factory:` 안에서
`async with sessionmaker_context(factory):`로 실행 경계를 연 뒤 유스케이스를 호출한다.

**1.0.3의 `REQUIRED`에는 rollback-only 표시가 없다.** 내부 작업이 Python 예외를
발생시켰어도 바깥 함수가 이를 잡고 정상 종료하면 내부 변경까지 커밋될 수 있다.
전체 롤백이 필요하면 예외를 최상위 `@transactional` 밖으로 전달한다.
내부 실패만 되돌리고 계속하려면 `NESTED`를 사용한다.

`ContextVar`는 자식 태스크에 상속된다. 하나의 트랜잭션 안에서 DB 작업을
`asyncio.gather()`로 병렬 실행하면 같은 `AsyncSession`을 공유하므로, 해당 작업은 순차 실행한다.
HTTP 요청과 독립적인 배치는 자체 세션 팩토리 컨텍스트를 열어 실행한다.
여러 DB나 외부 결제 API에 걸친 분산 트랜잭션은 제공하지 않는다.

낙관적 잠금의 버전 충돌(`StaleDataError`)은 HTTP 409로 변환하며 DB 오류 내용은 노출하지 않는다.
유스케이스의 `처리` 로그는 함수 본문 실행을 뜻하고, 최상위 트랜잭션의 커밋 완료를 뜻하지 않는다.
커밋 중 예외도 실패 로그를 남기고 호출자에게 전달한다.

## 검사

| 테스트 경로 | 검증 대상 |
| --- | --- |
| `tests/unit/` | DB 없이 도메인·유스케이스·설정·로그 검증. Repository는 테스트 대역 사용, 실제 데코레이터는 DB 연결 없이 실행 |
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
