import aws_cdk as cdk
from aws_cdk.assertions import Template
from infrastructure.infrastructure_stack import InfrastructureStack
from unittest.mock import patch

# Wir blockieren jeden potenziellen Cloud-Lookup über ein sauberes Test-Environment
TEST_ENV = cdk.Environment(account="123456789012", region="eu-central-1")

@patch('aws_cdk.Stack.of')
def test_infrastructure_components(mock_stack_of):
    app = cdk.App()
    stack = InfrastructureStack(app, "TestStack", env=TEST_ENV)
    template = Template.from_stack(stack)
    
    # 1. TEST: Existiert das ECR Repository mit dem korrekten Namen?
    template.has_resource_properties("AWS::ECR::Repository", {
        "RepositoryName": "calospro-repo"
    })
    
    # 2. TEST: Wurde das VPC mit dem richtigen Netzwerk-Bereich definiert?
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": "10.0.0.0/16"
    })
    
    # 3. TEST: Werden die beiden Security Groups sauber angelegt?
    template.resource_count_is("AWS::EC2::SecurityGroup", 2)
