#!/usr/bin/env bash
#
# cleanup.sh — Tear down all octopodai CloudFormation stacks and retained resources.
#
# Stacks are deleted in REVERSE dependency order. Resources that CloudFormation
# can't auto-delete (non-empty S3 buckets, ECR repos with images, RDS with
# deletion protection) are force-cleaned before stack deletion.
#
# Usage:
#   ./cleanup.sh              # defaults to octopodai / dev / us-east-1
#   ./cleanup.sh prod         # override environment
#   PROJECT=foo ENV=prod REGION=us-west-2 ./cleanup.sh
#
set -euo pipefail

PROJECT="${PROJECT:-octopodai}"
ENV="${ENV:-${1:-dev}}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[cleanup]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }

# ---------------------------------------------------------------------------
# Helper: delete a CloudFormation stack and wait
# ---------------------------------------------------------------------------
delete_stack() {
  local stack_name="$1"
  if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" &>/dev/null; then
    log "Deleting stack: $stack_name"
    aws cloudformation delete-stack --stack-name "$stack_name" --region "$REGION"
    aws cloudformation wait stack-delete-complete --stack-name "$stack_name" --region "$REGION"
    log "Deleted: $stack_name"
  else
    warn "Stack not found (skipping): $stack_name"
  fi
}

# ---------------------------------------------------------------------------
# Helper: empty and delete an S3 bucket
# ---------------------------------------------------------------------------
empty_and_delete_bucket() {
  local bucket="$1"
  if aws s3api head-bucket --bucket "$bucket" --region "$REGION" &>/dev/null; then
    log "Emptying S3 bucket: $bucket"
    aws s3 rm "s3://${bucket}" --recursive --region "$REGION"
    # Also remove any versioned objects / delete markers
    local versions
    versions=$(aws s3api list-object-versions --bucket "$bucket" --region "$REGION" \
      --query '{Objects: [].{Key:Key,VersionId:VersionId}}' --output json 2>/dev/null || echo '{"Objects":null}')
    if echo "$versions" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('Objects') else 1)" 2>/dev/null; then
      echo "$versions" | aws s3api delete-objects --bucket "$bucket" --region "$REGION" --delete file:///dev/stdin &>/dev/null || true
    fi
    log "Deleting S3 bucket: $bucket"
    aws s3api delete-bucket --bucket "$bucket" --region "$REGION" || warn "Could not delete bucket $bucket"
  else
    warn "Bucket not found (skipping): $bucket"
  fi
}

# ---------------------------------------------------------------------------
# Helper: delete all images in an ECR repository
# ---------------------------------------------------------------------------
empty_ecr_repo() {
  local repo="$1"
  if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &>/dev/null; then
    log "Deleting all images in ECR repo: $repo"
    local image_ids
    image_ids=$(aws ecr list-images --repository-name "$repo" --region "$REGION" --query 'imageIds[*]' --output json)
    if [ "$image_ids" != "[]" ] && [ -n "$image_ids" ]; then
      aws ecr batch-delete-image --repository-name "$repo" --region "$REGION" --image-ids "$image_ids" &>/dev/null || true
    fi
  else
    warn "ECR repo not found (skipping): $repo"
  fi
}

# ---------------------------------------------------------------------------
# Helper: delete a Secrets Manager secret (force, no recovery window)
# ---------------------------------------------------------------------------
delete_secret() {
  local secret_name="$1"
  if aws secretsmanager describe-secret --secret-id "$secret_name" --region "$REGION" &>/dev/null; then
    log "Force-deleting secret: $secret_name"
    aws secretsmanager delete-secret --secret-id "$secret_name" --force-delete-without-recovery --region "$REGION" || true
  else
    warn "Secret not found (skipping): $secret_name"
  fi
}

# ---------------------------------------------------------------------------
# Helper: disable RDS deletion protection
# ---------------------------------------------------------------------------
disable_rds_deletion_protection() {
  local db_id="$1"
  if aws rds describe-db-instances --db-instance-identifier "$db_id" --region "$REGION" &>/dev/null; then
    log "Disabling deletion protection on RDS: $db_id"
    aws rds modify-db-instance --db-instance-identifier "$db_id" --no-deletion-protection --apply-immediately --region "$REGION" &>/dev/null || true
    # Wait a bit for modification to apply
    sleep 5
  fi
}

# ===========================================================================
echo ""
echo "========================================================"
echo "  Octopod Infrastructure Cleanup"
echo "  Project:  $PROJECT"
echo "  Env:      $ENV"
echo "  Region:   $REGION"
echo "  Account:  $ACCOUNT_ID"
echo "========================================================"
echo ""
read -rp "Are you sure you want to DELETE ALL infrastructure? (type 'yes' to confirm): " confirm
if [ "$confirm" != "yes" ]; then
  err "Aborted."
  exit 1
fi

# ===========================================================================
# Phase 1: Clean retained resources that block stack deletion
# ===========================================================================
log "Phase 1: Cleaning retained resources..."

# S3 buckets (created by CICD pipeline stacks)
empty_and_delete_bucket "python-codepipeline-${REGION}-${ACCOUNT_ID}"
empty_and_delete_bucket "nextjs-codepipeline-${REGION}-${ACCOUNT_ID}"

# ECR repositories (created by code build stacks)
empty_ecr_repo "${PROJECT}-${ENV}"

# Secrets Manager secrets (created by db stacks)
delete_secret "${PROJECT}-${ENV}-qdrant-cloud"
delete_secret "${PROJECT}-${ENV}-opensearch-master"
# RDS-managed secret (name is auto-generated, find by tag or prefix)
for arn in $(aws secretsmanager list-secrets --region "$REGION" \
  --filters Key=name,Values="rds" Key=tag-key,Values=Name Key=tag-value,Values="${PROJECT}-${ENV}" \
  --query 'SecretList[*].ARN' --output text 2>/dev/null); do
  delete_secret "$arn"
done

# Disable RDS deletion protection (prod has it enabled)
# The DB identifier is auto-generated by CFN; find it via stack output
RDS_STACK="${PROJECT}-${ENV}-postgress-db-stack"
DB_ENDPOINT=$(aws cloudformation describe-stacks --stack-name "$RDS_STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DBEndpoint'].OutputValue" --output text 2>/dev/null || echo "")
if [ -n "$DB_ENDPOINT" ] && [ "$DB_ENDPOINT" != "None" ]; then
  # Extract DB instance identifier from the endpoint (format: <id>.<region>.rds.amazonaws.com)
  DB_INSTANCE_ID=$(echo "$DB_ENDPOINT" | cut -d. -f1)
  disable_rds_deletion_protection "$DB_INSTANCE_ID"
fi

# ===========================================================================
# Phase 2: Delete stacks in reverse dependency order
# ===========================================================================
log "Phase 2: Deleting CloudFormation stacks (reverse order)..."

# Tier 5: DNS & CICD pipelines (depend on ECS services)
delete_stack "${PROJECT}-${ENV}-dns-records-stack"
delete_stack "${PROJECT}-${ENV}-nextjs-cicd-pipeline-stack"
delete_stack "${PROJECT}-${ENV}-python-cicd-pipeline-stack"

# Tier 4: ECS services (depend on cluster, network, code-build)
delete_stack "${PROJECT}-${ENV}-nextjs-ecs-stack"
delete_stack "${PROJECT}-${ENV}-python-ecs-stack"

# Tier 3: Code build stacks (depend on ECR — already emptied)
delete_stack "${PROJECT}-${ENV}-nextjs-code-build-stack"
delete_stack "${PROJECT}-${ENV}-python-code-build-stack"

# Tier 2: Database & data stores (depend on network)
delete_stack "${PROJECT}-${ENV}-opensearch-stack"
delete_stack "${PROJECT}-${ENV}-qdrant-cloud-stack"
delete_stack "${PROJECT}-${ENV}-postgress-db-stack"

# Tier 1: ECS cluster (depends on network)
delete_stack "${PROJECT}-${ENV}-ecs-cluster-stack"

# Tier 0: Network (foundation — delete last)
delete_stack "${PROJECT}-${ENV}-network-stack"

# ===========================================================================
# Phase 3: Final sweep — catch orphaned resources
# ===========================================================================
log "Phase 3: Final sweep for orphaned resources..."

# Check for any remaining secrets with our project prefix
for secret_name in $(aws secretsmanager list-secrets --region "$REGION" \
  --filters Key=name,Values="${PROJECT}-${ENV}" \
  --query 'SecretList[*].Name' --output text 2>/dev/null); do
  delete_secret "$secret_name"
done

# Check for CloudWatch log groups left behind by ECS tasks
for log_group in $(aws logs describe-log-groups --region "$REGION" \
  --log-group-name-prefix "/ecs/${PROJECT}-${ENV}" \
  --query 'logGroups[*].logGroupName' --output text 2>/dev/null); do
  log "Deleting log group: $log_group"
  aws logs delete-log-group --log-group-name "$log_group" --region "$REGION" || true
done

echo ""
log "Cleanup complete."
echo ""
