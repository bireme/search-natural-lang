#!make

.PHONY: dev_build dev_run dev_start dev_stop dev_down dev_logs dev_sh dev_run_local dev_test \
        build start stop down logs sh

IMAGE_NAME := search-ui
CONTAINER_NAME := search-ui
DOCKER_FLAGS := -p 8000:8000 --env-file .env --add-host host.docker.internal:host-gateway
args ?=

# Development targets (volume-mounted code + hot-reload)
dev_build:
	@docker build --target dev -t $(IMAGE_NAME):dev .

dev_run:
	@docker run --rm --name $(CONTAINER_NAME) $(DOCKER_FLAGS) -v $$(pwd):/app $(IMAGE_NAME):dev

dev_start:
	@docker run -d --name $(CONTAINER_NAME) $(DOCKER_FLAGS) -v $$(pwd):/app $(IMAGE_NAME):dev

dev_stop:
	@docker stop $(CONTAINER_NAME)

dev_down:
	@docker stop $(CONTAINER_NAME) && docker rm $(CONTAINER_NAME)

dev_logs:
	@docker logs -f $(CONTAINER_NAME)

dev_sh:
	@docker run --rm -it $(DOCKER_FLAGS) -v $$(pwd):/app $(IMAGE_NAME):dev sh

dev_run_local:
	@uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev_test:
	@docker run --rm $(DOCKER_FLAGS) -v $$(pwd):/app $(IMAGE_NAME):dev \
		sh -c "uv run pytest $(args)"

# Production targets (code baked into image)
build:
	@docker build --target production -t $(IMAGE_NAME):latest .

start:
	@docker run -d --name $(CONTAINER_NAME) $(DOCKER_FLAGS) $(IMAGE_NAME):latest

stop:
	@docker stop $(CONTAINER_NAME)

down:
	@docker stop $(CONTAINER_NAME) && docker rm $(CONTAINER_NAME)

logs:
	@docker logs -f $(CONTAINER_NAME)

sh:
	@docker run --rm -it $(DOCKER_FLAGS) $(IMAGE_NAME):latest sh
