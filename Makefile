.PHONY: up down ingest verify seed test reset logs package

up:            ## 전체 기동 (DB + API + 화면)
	docker compose up --build

down:
	docker compose down

reset:         ## DB 볼륨까지 초기화
	docker compose down -v

logs:
	docker compose logs -f api

ingest:        ## 원본 JSON에서 파이프라인 전체 재실행 (data/raw 필요)
	docker compose exec api python -m pipeline.run --all

verify:        ## 인수 기준 검사 (실패 시 종료코드 1)
	docker compose exec api python -m pipeline.run --verify

seed:          ## 현재 DB 상태를 backend/db/02_seed.sql로 덤프
	docker compose exec api python -m pipeline.run --dump-seed

test:          ## 인수 기준 회귀 테스트
	docker compose exec api python -m pytest tests/ -q

package:       ## 제출용 zip 생성
	@rm -rf dist && mkdir -p dist/pkg
	@rsync -a --exclude-from=.pkgignore ./ dist/pkg/
	@cd dist/pkg && zip -qr9 "../roadwatch_소스코드.zip" .
	@echo "생성: dist/roadwatch_소스코드.zip  ($$(du -h dist/roadwatch_소스코드.zip | cut -f1))"
