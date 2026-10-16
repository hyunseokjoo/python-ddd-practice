# Python DDD Practice

FastAPI·Pydantic v2·SQLAlchemy로 주문 도메인의 DDD, CQRS, 명시적 트랜잭션 경계를 연습한다.
`Order`가 업무 규칙을 담당하고, 공통 요청 경계의 SQLAlchemy 트랜잭션이 모든 변경을 함께 커밋하거나 롤백한다.
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
공통 `get_request_container()`가 요청마다 세션과 트랜잭션을 열고,
`RequestContainer`를 통해 같은 세션을 모든 Repository에 주입한다.
API는 컨테이너에 등록된 비동기 유스케이스를 `await`한다.

FastAPI의 `Depends`는 요청 컨테이너 연결부 한 곳에만 둔다. `scope="function"`으로
설정해 응답 전송 전에 커밋·세션 종료를 마친다. 커밋 실패가 성공 응답으로 처리되지 않는다.

환경변수의 DB URL은 기존과 같다. PostgreSQL은 psycopg의 비동기 연결을 쓰며,
MySQL의 `mysql+pymysql` URL은 앱 안에서 `mysql+aiomysql`로 변환한다.
Alembic은 기존 동기 드라이버를 사용한다.

## 트랜잭션 경계

**요청 전체를 하나의 트랜잭션으로 처리한다.** 공통 요청 경계에서만 아래 컨텍스트를 실행한다.

```python
async with factory() as session, session.begin():
    yield container.request_container(session=session)
```

- 모든 유스케이스가 성공하면 공통 경계에서 한 번 자동 커밋한다.
- 예외·취소가 경계 밖으로 나오면 요청의 변경을 모두 롤백한다.
- Application은 Repository로 업무만 수행한다. Session을 인자로 받거나 begin·commit·rollback하지 않는다.
- Repository는 주입받은 세션으로 SQL과 필요한 flush만 실행한다.
- 조회도 같은 요청 세션을 공유한다. 조회 뒤 다른 유스케이스가 변경해도 새 트랜잭션을 중첩하지 않는다.

같은 요청에서 유스케이스 두 개를 호출해도 첫 함수가 반환될 때 커밋하지 않는다.
둘째 함수가 실패하면 첫 함수가 수행한 변경도 함께 롤백된다.
트랜잭션 데코레이터나 별도 UoW 구현 없이, [SQLAlchemy의 상위 트랜잭션 경계](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html#session-subtransaction-behavior-removed)와
명시적인 세션 주입으로 작업들을 묶는다.

CLI·배치에서는 요청 의존성이 없으므로 실행 진입점에서 같은 역할의 경계를 연다.

```python
from app.bootstrap.container import RequestContainer
from app.domains.orders.application.create_order import CreateOrderCommand
from app.shared.database.connection import open_database


async def create_two_orders(database_url: str):
    async with open_database(database_url) as factory:
        async with factory.begin() as session:
            container = RequestContainer(session=session)
            await container.orders().create_order(CreateOrderCommand())
            await container.orders().create_order(CreateOrderCommand())
        # 공통 경계를 정상 종료할 때 두 작업을 함께 자동 커밋한다.
```

내부 Python 예외를 잡고 정상 종료하면 앞선 변경이 커밋될 수 있다.
전체 롤백이 필요하면 예외를 공통 경계 밖으로 전달한다. 자동 rollback-only 표시나
`REQUIRES_NEW` 같은 전파 정책은 구현하지 않는다.
하나의 `AsyncSession`으로 DB 작업을 병렬 실행하지 않으며, 요청 종료 후 실행할
백그라운드 작업에는 요청 세션·컨테이너를 전달하지 않고 새 세션을 연다.

세션을 만들자마자 DB 연결을 점유하는 것은 아니지만, 첫 DB 접근 후 트랜잭션이 끝날 때까지는
연결을 점유할 수 있다. 외부 API 대기처럼 긴 작업이 포함되면 요청 범위의 적절성을 검토한다.
조회 전용 요청도 같은 정리 절차를 사용하며, 읽기 전용 제약을 강제하는 설정은 아니다.

낙관적 잠금의 버전 충돌(`StaleDataError`)은 HTTP 409로 변환하며 DB 오류 내용은 노출하지 않는다.
유스케이스의 `처리` 로그는 업무 함수 실행을 뜻하고, 요청 커밋 완료를 뜻하지 않는다.
커밋 중 예외도 공통 요청 경계에서 실패 로그를 남기고 호출자에게 전달한다.

## 검사

| 테스트 경로 | 검증 대상 |
| --- | --- |
| `tests/unit/` | DB 없이 도메인·유스케이스·설정·로그 검증. Repository는 테스트 대역 사용 |
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
