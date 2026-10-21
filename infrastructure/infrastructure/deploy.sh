#!/bin/bash
export AWS_ACCESS_KEY_ID="AKIA6GBMA2RBBWYTOBVX"
export AWS_SECRET_ACCESS_KEY="30+CE4olvJDFn791L8AXX57QW+bEU+S4Bgd8X96"
export AWS_DEFAULT_REGION="eu-central-1"
export JSII_RUNTIME_PACKAGE_CACHE="disabled"

echo "Starte CDK Bootstrap..."
cdk bootstrap aws://691745415276/eu-central-1
