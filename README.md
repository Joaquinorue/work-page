# Portfolio site on AWS with Pulumi

This project provisions the infrastructure for the personal portfolio website hosted at joaquinorue.work and its API at api.joaquinorue.work.

## What it includes

- Static website hosted on Amazon S3
- CloudFront distribution with HTTPS and custom domain
- Route53 records for the root domain and www subdomain
- ACM certificate for TLS
- Lambda + API Gateway API for a small CRUD service
- DynamoDB table for content persistence
- CV asset served from a dedicated S3 origin behind CloudFront

## Architecture

- Frontend: static HTML served from S3
- CDN: CloudFront in front of the S3 bucket
- DNS: Route53 managed zone for joaquinorue.work
- Security: ACM certificate and CloudFront Origin Access Control
- API: AWS Lambda behind API Gateway HTTP API and custom domain
- Storage: DynamoDB table for portfolio content records

## Prerequisites

- Python 3.12+
- Pulumi CLI installed and configured
- AWS credentials configured in your environment
- A Route53 hosted zone for the domain already created or managed via AWS

## Local setup

1. Create and activate a virtual environment:

```bash
cd Pagina
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure the Pulumi stack:

```bash
pulumi stack select dev
```

If the stack does not exist yet:

```bash
pulumi stack init dev
```

4. Deploy the infrastructure:

```bash
pulumi up
```

5. To update the static website after modifying files in the site folder:

```bash
pulumi up
```

## Folder structure

```text
Pagina/
├── __main__.py          # Pulumi infrastructure definition
├── requirements.txt     # Python dependencies
├── Pulumi.yaml          # Pulumi project definition
├── Pulumi.dev.yaml      # Stack configuration
├── site/                # Static website files
│   ├── index.html
│   ├── error.html
│   └── ...
├── lambda/
│   └── handler.py       # API Lambda function
├── test-events/         # Sample API payloads
└── README.md
```

## Useful commands

```bash
pulumi preview
pulumi up --yes
pulumi destroy
pulumi stack output
```

## Notes

The site content is stored in the S3 bucket managed by Pulumi, and the public distribution is served via CloudFront. The Lambda API is configured with a custom domain under api.joaquinorue.work.
