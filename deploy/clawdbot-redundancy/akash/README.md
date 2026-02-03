# Akash Network Deployment Guide

Deploy ClawdBot on decentralized GPU compute via Akash Network.

## Why Akash?

- **Cost**: ~$1.40/hr for H200 GPU vs $4.33 on AWS
- **Decentralization**: No single point of failure
- **GPU Access**: RTX 4090, A100, H100 available
- **Permissionless**: No KYC, deploy anywhere

## Prerequisites

1. **Install Akash CLI**
   ```bash
   curl -sSfL https://raw.githubusercontent.com/akash-network/provider/main/install.sh | sh
   ```

2. **Get AKT Tokens**
   - Purchase AKT on exchanges (Osmosis, Kraken)
   - Transfer to your Akash wallet

3. **Create Wallet**
   ```bash
   akash keys add clawdbot-wallet
   akash keys show clawdbot-wallet -a  # Save this address
   ```

## Deploy Steps

### 1. Fund Your Wallet
```bash
# Check balance
akash query bank balances $(akash keys show clawdbot-wallet -a)

# You need ~50 AKT for initial deployment (~1 week of compute)
```

### 2. Create Certificate
```bash
akash tx cert create client --from clawdbot-wallet --chain-id akashnet-2
```

### 3. Deploy
```bash
cd deploy/clawdbot-redundancy/akash

# Create deployment
akash tx deployment create deploy.yaml \
  --from clawdbot-wallet \
  --chain-id akashnet-2 \
  --node https://rpc.akashnet.net:443

# Note the DSEQ (deployment sequence) from output
```

### 4. Accept Bid
```bash
# List bids
akash query market bid list \
  --owner $(akash keys show clawdbot-wallet -a) \
  --dseq $DSEQ

# Accept a bid
akash tx market lease create \
  --dseq $DSEQ \
  --gseq 1 \
  --oseq 1 \
  --provider $PROVIDER_ADDRESS \
  --from clawdbot-wallet
```

### 5. Send Manifest
```bash
akash provider send-manifest deploy.yaml \
  --dseq $DSEQ \
  --provider $PROVIDER_ADDRESS \
  --from clawdbot-wallet
```

### 6. Get Endpoint
```bash
akash provider lease-status \
  --dseq $DSEQ \
  --provider $PROVIDER_ADDRESS

# Look for forwarded_ports to get your public URL
```

## Cost Optimization

| Configuration | Hourly Cost | Use Case |
|--------------|-------------|----------|
| CPU only (4 cores, 8GB) | ~$0.10/hr | Light workloads |
| RTX 4090 | ~$0.80/hr | Local inference |
| A100 | ~$1.40/hr | Heavy inference |
| H100 | ~$2.00/hr | Fine-tuning |

## Monitoring

```bash
# Check deployment status
akash query deployment get --owner $(akash keys show clawdbot-wallet -a) --dseq $DSEQ

# View logs
akash provider lease-logs --dseq $DSEQ --provider $PROVIDER_ADDRESS
```

## Shutdown

```bash
akash tx deployment close --dseq $DSEQ --from clawdbot-wallet
```

## Integration with Tailscale

Pass your Tailscale auth key as environment variable:
```yaml
env:
  - TAILSCALE_AUTHKEY=tskey-auth-xxx
```

This allows the Akash-deployed bot to join your mesh network.
