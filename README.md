# CalosPro ECS Pipeline & Cloud Infrastructure

This repository contains the complete, production-ready cloud infrastructure and CI/CD automation pipeline for the **CalosPro FastAPI application**. The entire infrastructure is declaratively defined as code using the **AWS CDK (Cloud Development Kit) in Python** and is thoroughly validated with automated unit tests.

---

## 🏗️ Architecture Overview

The infrastructure design follows AWS well-architected best practices to ensure maximum security, high availability, and cost optimization:

### 1. Networking & Transport Security (VPC & ALB)
*   **Multi-AZ VPC:** A dedicated virtual network (`10.0.0.0/16`) segmented into public subnets (for load balancer traffic ingestion) and private subnets with egress (for container task execution) spanning across two availability zones (`eu-central-1a`, `eu-central-1b`).
*   **Application Load Balancer (ALB):** Ingests public traffic on port 80 and enforces a permanent **HTTP-to-HTTPS redirect (Port 443)**. It actively monitors container health via the application's `/health` endpoint.
*   **Network Isolation:** The Fargate containers are completely isolated within the private subnets. The associated security group strictly restricts inbound traffic to requests originating *only* from the ALB on port 8000.

### 2. Serverless Container Orchestration (ECS & Auto Scaling)
*   **ECS Fargate Service:** Orchestrates container execution serverlessly, eliminating infrastructure maintenance. It runs on a cost-efficient resource tier of 256 CPU units (0.25 vCPU) and 512 MiB of RAM.
*   **Zero-Downtime Deployments:** A rolling update strategy (`min_healthy_percent=100`, `max_healthy_percent=200`) guarantees zero downtime during code updates. An active **Deployment Circuit Breaker** automatically rolls back failed deployments to the last stable state.
*   **Target Tracking Auto Scaling:** Dynamically scales the container task count between **1 and 5 replicas** whenever the aggregate CPU utilization exceeds 70% or memory allocation breaches 75%.

### 3. Security, Hardening & Telemetry (KMS & CloudWatch)
*   **At-Rest Encryption:** A Customer-Managed **AWS KMS Key** with mandatory automatic key rotation enabled cryptographically hardens the ECR container registry and associated resource layers.
*   **Storage Hygiene (Lifecycle Policy):** Automatically prunes orphaned build layers and untagged images after 14 days to minimize ECR storage costs.
*   **CloudWatch Monitoring:** Three sharp metric alarms protect platform health:
    *   *CPU Alarm:* Triggers if task compute usage is ≥ 80% for 3 consecutive minutes.
    *   *Memory Alarm:* Triggers if task RAM consumption is ≥ 85% for 3 consecutive minutes.
    *   *5XX Gateway Alarm:* A critical alert that fires if the ALB records more than 10 internal server errors (5XX) within a 1-minute window.

---

## 🚀 CI/CD Pipeline (GitHub Actions)

Continuous Integration and Continuous Deployment are orchestrated via `.github/workflows/deploy.yml`. Upon every code change pushed to the `main` or `master` branches, GitHub Actions automates the following lifecycle:

1.  **Checkout:** Clones the codebase into the ephemeral runner workspace.
2.  **AWS Authentication:** Securely authenticates against the AWS Cloud tier utilizing encrypted GitHub Repository Secrets.
3.  **Docker Build:** Compiles the application image locally on the runner and tags it using metadata from the authenticated Amazon ECR registry.
4.  **Trivy Security Scan:** Runs a Shift-Left static application security testing (SAST) container scan via Aqua Security's `trivy-action`, searching for HIGH and CRITICAL vulnerabilities.
5.  **ECR Push:** Upon clearing the security gate, the verified image is securely pushed into the private Amazon ECR repository.

---

## 🛠️ Quick Start: Local Development & Validation

To review the project code locally, leverage the isolated virtual environment, and run validation scripts, execute the following commands within the project root:

### 1. Navigate to the Infrastructure Scope
```bash
cd infrastructure
```

### 2. Activate the Python Virtual Environment
```bash
source .venv/bin/activate
```

### 3. Run Automated Unit Tests
The infrastructure components are mocked locally in memory via `pytest` and the `aws_cdk.assertions` framework, eliminating the need for a live AWS connection:
```bash
pytest
```
*All core declarations (ECR repository schema, VPC CIDR mapping, and firewall counts) are successfully validated (`2 passed`).*

### 4. Synthesize CloudFormation Templates
To locally compile the CDK python stack into standard AWS CloudFormation declarative code for auditing, run:
```bash
cdk synth
```

---

## ⚙️ Production Deployment Prerequisites

Before deploying this stack into a live, production-facing AWS Account, ensure the following steps are completed:

1.  **Provision SSL/TLS Certificate:** To support the encrypted HTTPS protocol tier on port 443, request a public certificate inside *AWS Certificate Manager (ACM)* and map its ARN string descriptor onto the Load Balancer HTTPS listener construct.
2.  **Populate GitHub Actions Secrets:** Populate your target GitHub repository under *Settings -> Secrets and variables -> Actions* with valid, long-lived programmatic keys:
    *   `AWS_ACCESS_KEY_ID`
    *   `AWS_SECRET_ACCESS_KEY`
