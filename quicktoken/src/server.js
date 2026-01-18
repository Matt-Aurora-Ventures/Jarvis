require('dotenv').config();
const express = require('express');
const cors = require('cors');
const multer = require('multer');
const Stripe = require('stripe');
const { BagsSDK } = require('@bagsfm/bags-sdk');
const { Connection, Keypair, PublicKey } = require('@solana/web3.js');
const path = require('path');
const fs = require('fs');

const app = express();
const upload = multer({ storage: multer.memoryStorage() });
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

// Initialize Bags SDK
const connection = new Connection(process.env.SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com');
const bags = new BagsSDK(process.env.BAGS_API_KEY, connection);

// In-memory store for pending launches (use Redis/DB in production)
const pendingLaunches = new Map();

app.use(cors());
app.use(express.static('public'));

// Stripe webhook needs raw body
app.post('/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
  const sig = req.headers['stripe-signature'];
  let event;

  try {
    event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
  } catch (err) {
    console.error('Webhook signature verification failed:', err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object;
    const launchId = session.metadata.launchId;

    if (pendingLaunches.has(launchId)) {
      const launch = pendingLaunches.get(launchId);
      launch.paid = true;
      console.log(`Payment confirmed for launch ${launchId}`);
    }
  }

  res.json({ received: true });
});

app.use(express.json());

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Step 1: Create token info and get preview
app.post('/api/token/prepare', upload.single('image'), async (req, res) => {
  try {
    const { name, symbol, description, twitter, telegram, website } = req.body;
    const imageBuffer = req.file?.buffer;

    if (!name || !symbol || !description) {
      return res.status(400).json({ error: 'Name, symbol, and description are required' });
    }

    if (!imageBuffer) {
      return res.status(400).json({ error: 'Image is required' });
    }

    // Create token info via Bags API
    const tokenInfo = await bags.tokenLaunch.createTokenInfoAndMetadata({
      name,
      symbol,
      description,
      twitter: twitter || undefined,
      telegram: telegram || undefined,
      website: website || undefined,
      image: imageBuffer,
    });

    // Generate a launch ID
    const launchId = `launch_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Store pending launch
    pendingLaunches.set(launchId, {
      tokenInfo,
      name,
      symbol,
      description,
      paid: false,
      createdAt: new Date(),
    });

    // Clean up old pending launches (older than 1 hour)
    const oneHourAgo = Date.now() - 3600000;
    for (const [id, launch] of pendingLaunches) {
      if (new Date(launch.createdAt).getTime() < oneHourAgo) {
        pendingLaunches.delete(id);
      }
    }

    res.json({
      launchId,
      preview: {
        name,
        symbol,
        description,
        metadataUrl: tokenInfo.metadataUrl,
        imageUrl: tokenInfo.imageUrl,
      },
    });
  } catch (error) {
    console.error('Error preparing token:', error);
    res.status(500).json({ error: error.message || 'Failed to prepare token' });
  }
});

// Step 2: Create Stripe checkout session
app.post('/api/checkout', async (req, res) => {
  try {
    const { launchId } = req.body;

    if (!pendingLaunches.has(launchId)) {
      return res.status(404).json({ error: 'Launch not found' });
    }

    const launch = pendingLaunches.get(launchId);

    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: [
        {
          price: process.env.STRIPE_PRICE_ID, // $49 one-time
          quantity: 1,
        },
      ],
      mode: 'payment',
      success_url: `${req.headers.origin}/success?launchId=${launchId}`,
      cancel_url: `${req.headers.origin}/`,
      metadata: {
        launchId,
        tokenName: launch.name,
        tokenSymbol: launch.symbol,
      },
    });

    res.json({ checkoutUrl: session.url });
  } catch (error) {
    console.error('Error creating checkout:', error);
    res.status(500).json({ error: 'Failed to create checkout session' });
  }
});

// Step 3: Get launch transaction (after payment)
app.post('/api/token/launch', async (req, res) => {
  try {
    const { launchId, walletAddress, initialBuyLamports } = req.body;

    if (!pendingLaunches.has(launchId)) {
      return res.status(404).json({ error: 'Launch not found' });
    }

    const launch = pendingLaunches.get(launchId);

    if (!launch.paid) {
      return res.status(402).json({ error: 'Payment required' });
    }

    if (!walletAddress) {
      return res.status(400).json({ error: 'Wallet address is required' });
    }

    const launchWallet = new PublicKey(walletAddress);
    const tokenMint = Keypair.generate();

    // Create fee share config (you as partner + creator)
    const configResult = await bags.config.createFeeShareConfigWithPartnerKey({
      tokenMint: tokenMint.publicKey,
      partnerKey: new PublicKey(process.env.PARTNER_WALLET),
      feeClaimers: [
        {
          socialProvider: 'twitter',
          socialHandle: launch.tokenInfo.twitter || 'default',
          feeBps: 10000, // 100% of creator share goes to creator
        },
      ],
    });

    // Create launch transaction
    const launchTx = await bags.tokenLaunch.createLaunchTransaction({
      metadataUrl: launch.tokenInfo.metadataUrl,
      tokenMint: tokenMint.publicKey,
      launchWallet,
      initialBuyLamports: initialBuyLamports || 0,
      configKey: configResult.configKey,
    });

    // Serialize transaction for client signing
    const serializedTx = Buffer.from(launchTx.serialize()).toString('base64');
    const tokenMintSecret = Buffer.from(tokenMint.secretKey).toString('base64');

    res.json({
      transaction: serializedTx,
      tokenMint: tokenMint.publicKey.toBase58(),
      tokenMintSecret, // Client needs to sign with this
      configKey: configResult.configKey.toBase58(),
    });
  } catch (error) {
    console.error('Error creating launch transaction:', error);
    res.status(500).json({ error: error.message || 'Failed to create launch transaction' });
  }
});

// Check launch status
app.get('/api/token/status/:launchId', (req, res) => {
  const { launchId } = req.params;

  if (!pendingLaunches.has(launchId)) {
    return res.status(404).json({ error: 'Launch not found' });
  }

  const launch = pendingLaunches.get(launchId);
  res.json({
    paid: launch.paid,
    name: launch.name,
    symbol: launch.symbol,
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`QuickToken server running on port ${PORT}`);
  console.log(`Open http://localhost:${PORT} to access the app`);
});
