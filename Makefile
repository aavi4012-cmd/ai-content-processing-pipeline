.PHONY: build up down logs test

# 🚀 Build and start all services in detached mode
build:
	docker-compose up -d --build

# 🚀 Start all services (if already built)
up:
	docker-compose up -d

# 🛑 Stop all running services
down:
	docker-compose down

# 📜 View live logs of the API and Worker
logs:
	docker-compose logs -f api worker 

# 🧪 Run the unit test suite
test:
	pytest tests/ -v -W ignore
