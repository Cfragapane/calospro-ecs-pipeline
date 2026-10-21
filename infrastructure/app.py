#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infrastructure.infrastructure_stack import InfrastructureStack

app = cdk.App()

# Korrekte Umgebung mit deiner neuen Account-ID
aws_env = cdk.Environment(
    account="992382782363",
    region="eu-central-1"
)

InfrastructureStack(
    app, 
    "InfrastructureStack",
    env=aws_env
)

app.synth()
