from aws_cdk import (
    Stack,
    Duration,
    aws_ecr as ecr,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_kms as kms
)
from constructs import Construct

class InfrastructureStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------
        # 🔑 CALOSPRO-89 & 90: AWS KMS SCHLÜSSEL FÜR AT-REST VERSCHLÜSSELUNG
        # ---------------------------------------------------------
        # Erstellt einen Customer Managed Key zur Verschlüsselung von ECR und Logs
        kms_key = kms.Key(
            self, "CalosProEncryptionKey",
            alias="alias/calospro-infrastructure-key",
            description="KMS Key zur Verschluesselung der CalosPro Cloud-Ressourcen",
            enable_key_rotation=True # Sicherheits-Best-Practice
        )

        # ---------------------------------------------------------
        # 📦 EPIC: CREATE THE ECR REPOSITORY (CALOSPRO-61 & 63 - JETZT MIT KMS!)
        # ---------------------------------------------------------
        repository = ecr.Repository(
            self, "CalosProRepository",
            repository_name="calospro-repo",
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            encryption=ecr.RepositoryEncryption.KMS, # KMS Verschlüsselung aktivieren
            encryption_key=kms_key
        )

        repository.add_lifecycle_rule(
            description="Loesche ungetaggte Images nach 14 Tagen zur Kostenoptimierung",
            max_image_age=Duration.days(14),
            tag_status=ecr.TagStatus.UNTAGGED
        )

        # ---------------------------------------------------------
        # 🌐 EPIC: NETZWERK & LOAD BALANCER (CALOSPRO-65 bis 67)
        # ---------------------------------------------------------
        vpc = ec2.Vpc(
            self, "CalosProVpc",
            availability_zones=["eu-central-1a", "eu-central-1b"],
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24)
            ]
        )

        alb_sg = ec2.SecurityGroup(
            self, "AlbSecurityGroup",
            vpc=vpc,
            description="Erlaubt HTTP und HTTPS-Traffic von aussen zum Load Balancer",
            allow_all_outbound=True
        )
        alb_sg.add_ingress_rule(peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(80))
        alb_sg.add_ingress_rule(peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(443)) # HTTPS Port öffnen

        task_sg = ec2.SecurityGroup(
            self, "TaskSecurityGroup",
            vpc=vpc,
            description="Erlaubt Traffic ausschliesslich vom ALB zu den ECS Tasks",
            allow_all_outbound=True
        )
        task_sg.add_ingress_rule(peer=alb_sg, connection=ec2.Port.tcp(8000))

        alb = elbv2.ApplicationLoadBalancer(
            self, "CalosProALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg
        )

        # CALOSPRO-91 & 92: HTTP (Port 80) Listener mit automatischer HTTPS-Umleitung
        alb.add_listener(
            "HttpListener",
            port=80,
            default_action=elbv2.ListenerAction.redirect(
                port="443",
                protocol="HTTPS",
                permanent=True
            )
        )

        # Target Group erstellen für den HTTPS-Traffic (wird später an Port 443 gehängt)
        target_group = elbv2.ApplicationTargetGroup(
            self, "FastApiTargets",
            vpc=vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/health",
                protocol=elbv2.Protocol.HTTP,
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3
            )
        )

        # ---------------------------------------------------------
        # 🚢 EPIC: ECS CLUSTER & IAM ROLES (CALOSPRO-69 & 70)
        # ---------------------------------------------------------
        cluster = ecs.Cluster(self, "CalosProCluster", vpc=vpc, cluster_name="calospro-cluster")

        execution_role = iam.Role(
            self, "EcsTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("://amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )

        # ---------------------------------------------------------
        # 🚀 EPIC: ECS SERVICE & DEPLOYMENT (CALOSPRO-77 & 79)
        # ---------------------------------------------------------
        task_definition = ecs.FargateTaskDefinition(
            self, "CalosProTaskDef",
            memory_limit_mib=512,
            cpu=256,
            execution_role=execution_role
        )

        container = task_definition.add_container(
            "CalosProContainer",
            image=ecs.ContainerImage.from_ecr_repository(repository, "latest"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="calospro-app")
        )
        container.add_port_mappings(
            ecs.PortMapping(container_port=8000, protocol=ecs.Protocol.TCP)
        )

        fargate_service = ecs.FargateService(
            self, "CalosProFargateService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            security_groups=[task_sg],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            max_healthy_percent=200
        )

        target_group.add_target(fargate_service)

        # ---------------------------------------------------------
        # 📊 EPIC: MONITORING & CLOUDWATCH ALARMS (CALOSPRO-81 bis 84)
        # ---------------------------------------------------------
        cpu_metric = fargate_service.metric_cpu_utilization(period=Duration.minutes(1))
        cloudwatch.Alarm(
            self, "CalosProCpuHighAlarm", metric=cpu_metric, threshold=80, evaluation_periods=3, datapoints_to_alarm=3,
            alarm_description="Alarm bei hoher CPU-Auslastung der Fargate-Tasks.",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )

        memory_metric = fargate_service.metric_memory_utilization(period=Duration.minutes(1))
        cloudwatch.Alarm(
            self, "CalosProMemoryHighAlarm", metric=memory_metric, threshold=85, evaluation_periods=3, datapoints_to_alarm=3,
            alarm_description="Alarm bei hoher RAM-Auslastung der Fargate-Tasks.",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )

        http_5xx_metric = alb.metric_http_code_target(code=elbv2.HttpCodeTarget.TARGET_5XX_COUNT, period=Duration.minutes(1))
        cloudwatch.Alarm(
            self, "CalosProTarget5xxAlarm", metric=http_5xx_metric, threshold=10, evaluation_periods=1,
            alarm_description="Kritischer Alarm: Der Load Balancer registriert interne Serverfehler (5XX).",
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )

        # ---------------------------------------------------------
        # 📈 EPIC: ECS AUTO SCALING (CALOSPRO-85 bis 88)
        # ---------------------------------------------------------
        scaling_target = fargate_service.auto_scale_task_count(min_capacity=1, max_capacity=5)
        scaling_target.scale_on_cpu_utilization(
            "CpuAutoScaling", target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(300), scale_out_cooldown=Duration.seconds(60)
        )
        scaling_target.scale_on_memory_utilization(
            "MemoryAutoScaling", target_utilization_percent=75,
            scale_in_cooldown=Duration.seconds(300), scale_out_cooldown=Duration.seconds(60)
        )
