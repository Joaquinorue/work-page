"""Infrastructure for the joaquinorue.work portfolio site."""

import json
import mimetypes
import os

import pulumi
import pulumi_aws as aws


config = pulumi.Config()
domain_name = config.require("domainName")
sub_domain = config.get("subDomain") or "www"


zone = aws.route53.Zone(
    "portfolio-zone",
    name=domain_name,
    comment="Hosted zone del portfolio personal",
)

pulumi.export("zone_id", zone.zone_id)
pulumi.export("nameservers_para_tu_registrador", zone.name_servers)


cert = aws.acm.Certificate(
    "portfolio-cert",
    domain_name=domain_name,
    subject_alternative_names=[f"*.{domain_name}"],
    validation_method="DNS",
)


validation_option = cert.domain_validation_options[0]

cert_validation_record = aws.route53.Record(
    "portfolio-cert-validation-record",
    zone_id=zone.zone_id,
    name=validation_option.resource_record_name,
    type=validation_option.resource_record_type,
    records=[validation_option.resource_record_value],
    ttl=300,
    allow_overwrite=True,
)


cert_validation = aws.acm.CertificateValidation(
    "portfolio-cert-validation",
    certificate_arn=cert.arn,
    validation_record_fqdns=[cert_validation_record.fqdn],
)

pulumi.export("certificado_arn", cert.arn)
pulumi.export("certificado_estado", cert.status)

site_bucket = aws.s3.BucketV2(
    "portfolio-site",
    bucket="joaquinorue.work-portfolio",
)

aws.s3.BucketPublicAccessBlock(
    "portfolio-site-pab",
    bucket=site_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

site_dir = os.path.join(os.path.dirname(__file__), "site")

for filename in os.listdir(site_dir):
    filepath = os.path.join(site_dir, filename)
    content_type, _ = mimetypes.guess_type(filepath)

    aws.s3.BucketObjectv2(
        filename,
        bucket=site_bucket.id,
        key=filename,
        source=pulumi.FileAsset(filepath),
        content_type=content_type or "application/octet-stream",
    )

pulumi.export("bucket_name", site_bucket.bucket)

cv_bucket = aws.s3.get_bucket(bucket="cvjoaquinorue")

pulumi.export("cv_bucket_arn", cv_bucket.arn)

oac = aws.cloudfront.OriginAccessControl(
    "portfolio-oac",
    origin_access_control_origin_type="s3",
    signing_behavior="always",
    signing_protocol="sigv4",
)

distribution = aws.cloudfront.Distribution(
    "portfolio-distribution",
    enabled=True,
    default_root_object="index.html",
    price_class="PriceClass_100",
    aliases=[domain_name, f"{sub_domain}.{domain_name}"],
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            origin_id=site_bucket.arn,
            domain_name=site_bucket.bucket_regional_domain_name,
            origin_access_control_id=oac.id,
        ),
        aws.cloudfront.DistributionOriginArgs(
            origin_id=cv_bucket.arn,
            domain_name=cv_bucket.bucket_regional_domain_name,
            origin_access_control_id=oac.id,
        ),
    ],
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id=site_bucket.arn,
        viewer_protocol_policy="redirect-to-https",
        allowed_methods=["GET", "HEAD"],
        cached_methods=["GET", "HEAD"],
        compress=True,
        forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
            query_string=False,
            cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                forward="none",
            ),
        ),
        min_ttl=0,
        default_ttl=3600,
        max_ttl=86400,
    ),
    ordered_cache_behaviors=[
        aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
            path_pattern="/CV_Joaquin_Orue.pdf",
            target_origin_id=cv_bucket.arn,
            viewer_protocol_policy="redirect-to-https",
            allowed_methods=["GET", "HEAD"],
            cached_methods=["GET", "HEAD"],
            compress=True,
            forwarded_values=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesArgs(
                query_string=False,
                cookies=aws.cloudfront.DistributionOrderedCacheBehaviorForwardedValuesCookiesArgs(
                    forward="none",
                ),
            ),
            min_ttl=0,
            default_ttl=3600,
            max_ttl=86400,
        ),
    ],
    custom_error_responses=[
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=403,
            response_code=404,
            response_page_path="/error.html",
        ),
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=404,
            response_code=404,
            response_page_path="/error.html",
        ),
    ],
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none",
        ),
    ),
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        acm_certificate_arn=cert.arn,
        ssl_support_method="sni-only",
        minimum_protocol_version="TLSv1.2_2021",
    ),
    opts=pulumi.ResourceOptions(depends_on=[cert_validation]),
)

bucket_policy_document = pulumi.Output.all(site_bucket.arn, distribution.arn).apply(
    lambda args: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCloudFrontServicePrincipal",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudfront.amazonaws.com"},
                    "Action": "s3:GetObject",
                    "Resource": f"{args[0]}/*",
                    "Condition": {
                        "StringEquals": {
                            "AWS:SourceArn": args[1]
                        }
                    },
                }
            ],
        }
    )
)

aws.s3.BucketPolicy(
    "portfolio-site-bucket-policy",
    bucket=site_bucket.id,
    policy=bucket_policy_document,
)

for record_name, subject in [
    ("portfolio-dns-apex", domain_name),
    ("portfolio-dns-www", f"{sub_domain}.{domain_name}"),
]:
    aws.route53.Record(
        record_name,
        zone_id=zone.zone_id,
        name=subject,
        type="A",
        aliases=[
            aws.route53.RecordAliasArgs(
                name=distribution.domain_name,
                zone_id="Z2FDTNDATAQYW2",
                evaluate_target_health=False,
            )
        ],
    )

pulumi.export("distribution_id", distribution.id)
pulumi.export("distribution_domain_name", distribution.domain_name)
pulumi.export("sitio", f"https://{domain_name}")

content_table = aws.dynamodb.Table(
    "portfolio-content",
    name="portfolio-content",
    billing_mode="PAY_PER_REQUEST",
    hash_key="PK",
    range_key="SK",
    attributes=[
        aws.dynamodb.TableAttributeArgs(name="PK", type="S"),
        aws.dynamodb.TableAttributeArgs(name="SK", type="S"),
        aws.dynamodb.TableAttributeArgs(name="GSI1PK", type="S"),
        aws.dynamodb.TableAttributeArgs(name="GSI1SK", type="S"),
    ],
    global_secondary_indexes=[
        aws.dynamodb.TableGlobalSecondaryIndexArgs(
            name="GSI1",
            hash_key="GSI1PK",
            range_key="GSI1SK",
            projection_type="ALL",
        )
    ],
)

pulumi.export("tabla_dynamodb", content_table.name)

lambda_assume_role_policy = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
)

lambda_role = aws.iam.Role(
    "portfolio-api-lambda-role",
    assume_role_policy=lambda_assume_role_policy,
)

aws.iam.RolePolicyAttachment(
    "portfolio-api-lambda-logs",
    role=lambda_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
)

lambda_dynamodb_policy_document = content_table.arn.apply(
    lambda table_arn: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:GetItem",
                        "dynamodb:PutItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:Query",
                    ],
                    "Resource": [
                        table_arn,
                        f"{table_arn}/index/*",
                    ],
                }
            ],
        }
    )
)

aws.iam.RolePolicy(
    "portfolio-api-lambda-dynamodb",
    role=lambda_role.id,
    policy=lambda_dynamodb_policy_document,
)

pulumi.export("lambda_role_arn", lambda_role.arn)

api_lambda = aws.lambda_.Function(
    "portfolio-api-lambda",
    role=lambda_role.arn,
    runtime="python3.12",
    handler="handler.handler",
    code=pulumi.FileArchive("./lambda"),
    timeout=10,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={"TABLE_NAME": content_table.name},
    ),
)

pulumi.export("lambda_function_name", api_lambda.name)

api_domain = aws.apigatewayv2.DomainName(
    "portfolio-api-domain",
    domain_name=f"api.{domain_name}",
    domain_name_configuration=aws.apigatewayv2.DomainNameDomainNameConfigurationArgs(
        certificate_arn=cert.arn,
        endpoint_type="REGIONAL",
        security_policy="TLS_1_2",
    ),
    opts=pulumi.ResourceOptions(depends_on=[cert_validation]),
)

api = aws.apigatewayv2.Api(
    "portfolio-api",
    protocol_type="HTTP",
    cors_configuration=aws.apigatewayv2.ApiCorsConfigurationArgs(
        allow_origins=[
            f"https://{domain_name}",
            f"https://{sub_domain}.{domain_name}",
        ],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["content-type"],
        max_age=300,
    ),
)

lambda_integration = aws.apigatewayv2.Integration(
    "portfolio-api-integration",
    api_id=api.id,
    integration_type="AWS_PROXY",
    integration_uri=api_lambda.invoke_arn,
    integration_method="POST",
    payload_format_version="2.0",
)

route_keys = [
    "GET /items",
    "GET /items/{type}/{id}",
    "POST /items",
    "DELETE /items/{type}/{id}",
]

for route_key in route_keys:
    logical_name = "portfolio-api-route-" + (
        route_key.lower().replace(" ", "-").replace("/", "-").replace("{", "").replace("}", "")
    )
    aws.apigatewayv2.Route(
        logical_name,
        api_id=api.id,
        route_key=route_key,
        target=pulumi.Output.concat("integrations/", lambda_integration.id),
    )

stage = aws.apigatewayv2.Stage(
    "portfolio-api-stage",
    api_id=api.id,
    name="$default",
    auto_deploy=True,
)


aws.apigatewayv2.ApiMapping(
    "portfolio-api-mapping",
    api_id=api.id,
    domain_name=api_domain.id,
    stage=stage.id,
    api_mapping_key="",
)
aws.lambda_.Permission(
    "portfolio-api-lambda-permission",
    action="lambda:InvokeFunction",
    function=api_lambda.name,
    principal="apigateway.amazonaws.com",
    source_arn=pulumi.Output.concat(api.execution_arn, "/*/*"),
)

aws.route53.Record(
    "portfolio-dns-api",
    zone_id=zone.zone_id,
    name=f"api.{domain_name}",
    type="A",
    aliases=[
        aws.route53.RecordAliasArgs(
            name=api_domain.domain_name_configuration.target_domain_name,
            zone_id=api_domain.domain_name_configuration.hosted_zone_id,
            evaluate_target_health=False,
        )
    ],
)

pulumi.export("api_url", f"https://api.{domain_name}")

cv_bucket_policy_document = distribution.arn.apply(
    lambda distribution_arn: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCloudFrontServicePrincipal",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudfront.amazonaws.com"},
                    "Action": "s3:GetObject",
                    "Resource": f"{cv_bucket.arn}/*",
                    "Condition": {
                        "StringEquals": {
                            "AWS:SourceArn": distribution_arn
                        }
                    },
                }
            ],
        }
    )
)

aws.s3.BucketPolicy(
    "cv-bucket-policy",
    bucket=cv_bucket.id,
    policy=cv_bucket_policy_document,
)
