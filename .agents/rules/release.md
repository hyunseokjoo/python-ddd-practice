# 릴리스 노트

Claude·Codex 등 공용 에이전트는 GitHub의 릴리스 노트 작성 또는 태그 생성 전에 이 규칙을 읽는다.

## 버전과 작성 기준

- **태그:** `vX.Y.Z`(SemVer). 호환성 깨짐은 X, 기능 추가는 Y, 버그 수정만 있으면 Z를 올린다.
- **릴리스 이름:** `vX.Y.Z — <대표 변경 한 줄>`. 비교 기준은 직전 릴리스 태그다.
- **항목:** 이전 태그 이후 릴리스에 포함된 PR을 빠짐없이 한 번씩만 기록하고, 각 분류에서 번호 오름차순으로 정렬한다. 원문 제목·작성자를 사용하며 요약·상세 설명·Jira 키를 추가하지 않는다.
- **분류:** 제목 앞의 `[Jira 키]`는 분류할 때만 제외하고 타입을 읽는다. `feat` → Features, `fix` → Bug Fixes, `refactor`·`perf`·의존성 업그레이드 → Improvements, `docs` → Documentation, `chore`·`ci`·`build`·`test`·`style` → Other. 본문에 기록하는 원문 제목은 그대로 유지한다.
- **배포 주의사항:** PR 설명과 diff로 확인한 설정·DB 마이그레이션·재시작·런타임 버전 변경만 Deployment Notes에 한국어로 적는다. Changelog에는 이전 태그와 이번 태그의 비교 링크만 넣는다.

## 본문 템플릿

빈 섹션은 생략하고 영문 제목과 순서는 유지한다. PR은 `#번호`로 표기한다. 아래 `owner/repo`와 PR 번호·태그는 예시이므로 실제 저장소·PR·태그의 URL로 바꾼다.

- PR URL: `<저장소 URL>/pull/번호`
- 비교 URL: `<저장소 URL>/compare/이전태그...이번태그`

```markdown
## Features
- [#250](https://github.com/owner/repo/pull/250) <원문 제목> @<작성자>

## Bug Fixes
- [#251](https://github.com/owner/repo/pull/251) <원문 제목> @<작성자>

## Improvements
- [#252](https://github.com/owner/repo/pull/252) <원문 제목> @<작성자>

## Documentation
- [#254](https://github.com/owner/repo/pull/254) <원문 제목> @<작성자>

## Other
- [#255](https://github.com/owner/repo/pull/255) <원문 제목> @<작성자>

## Deployment Notes
- <확인된 배포 주의사항>

## Changelog
Full Changelog: [v1.0.0...v1.1.0](https://github.com/owner/repo/compare/v1.0.0...v1.1.0)
```

게시할 때는 위 Markdown을 본문으로 사용하며, 전체를 코드 블록으로 감싸지 않는다.

## 작성·게시 절차

1. GitHub 저장소·대상 브랜치·이전 태그를 확인하고, 포함된 PR의 제목·작성자·설명·diff를 조회한다.
2. 템플릿에 맞춰 저장소 루트의 `release-notes.md`를 작성한다. 이 파일은 커밋하지 않는다.
3. 버전·대상 브랜치·완성된 본문을 사용자에게 보여주고, 태그·릴리스 게시 승인을 받는다.
4. 승인된 내용으로 `gh release create`를 사용해 태그·릴리스를 만든다. 승인된 대상 브랜치는 `--target`, 릴리스 이름은 `--title`, 본문 파일은 `--notes-file release-notes.md`로 지정하고 결과를 확인한다.
