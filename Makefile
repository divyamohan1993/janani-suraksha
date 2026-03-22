.PHONY: help build precompute test run deploy destroy clean

PROJECT_ID ?= $(shell gcloud config get-value project 2>/dev/null)
REGION ?= asia-south1
SERVICE_NAME ?= janani-suraksha
IMAGE_TAG ?= latest
REGISTRY = $(REGION)-docker.pkg.dev/$(PROJECT_ID)/janani-suraksha

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

precompute: ## Generate precomputed O(1) data tables
	python -m app.precompute.generate_risk_table
	python -m app.precompute.generate_facility_graph
	python -m app.precompute.generate_hb_trajectories

test: ## Run all tests
	python -m pytest tests/ -v

run: ## Run locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

build: ## Build Docker image
	docker build -t $(SERVICE_NAME):$(IMAGE_TAG) .

push: ## Push image to Artifact Registry
	docker tag $(SERVICE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(SERVICE_NAME):$(IMAGE_TAG)
	docker push $(REGISTRY)/$(SERVICE_NAME):$(IMAGE_TAG)

infra: ## Apply Terraform infrastructure
	cd infra && terraform init && terraform apply -auto-approve \
		-var="project_id=$(PROJECT_ID)" \
		-var="region=$(REGION)" \
		-var="service_name=$(SERVICE_NAME)" \
		-var="image_tag=$(IMAGE_TAG)"

deploy: build push infra ## Full deployment: build + push + terraform apply
	@echo ""
	@echo "Deployed! Service URL:"
	@cd infra && terraform output -raw service_url
	@echo ""

destroy: ## Tear down all infrastructure
	cd infra && terraform destroy -auto-approve \
		-var="project_id=$(PROJECT_ID)" \
		-var="region=$(REGION)"

clean: ## Clean local artifacts
	rm -rf data/ __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

logs: ## View Cloud Run logs
	gcloud run services logs read $(SERVICE_NAME) --region $(REGION) --limit 50
