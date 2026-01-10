/**
 * Token Metadata Setup for $KR8TIV
 * Prompt #31: Set up proper token metadata on Solana
 */

import {
  Metaplex,
  keypairIdentity,
  bundlrStorage,
  toMetaplexFile,
} from "@metaplex-foundation/js";
import {
  Connection,
  Keypair,
  PublicKey,
  clusterApiUrl,
} from "@solana/web3.js";
import * as fs from "fs";
import * as path from "path";

// Token Configuration
const TOKEN_CONFIG = {
  name: "KR8TIV",
  symbol: "$KR8TIV",
  description:
    "The native utility token powering the JARVIS autonomous AI trading ecosystem. Stake to earn SOL rewards from trading fees.",
  image: "kr8tiv_logo.png",
  external_url: "https://jarvis.ai",
  attributes: [
    { trait_type: "Category", value: "Utility Token" },
    { trait_type: "Network", value: "Solana" },
    { trait_type: "Use Case", value: "Staking & Governance" },
  ],
  properties: {
    files: [
      {
        uri: "", // Will be set after upload
        type: "image/png",
      },
    ],
    category: "image",
    creators: [
      {
        address: "", // Will be set from keypair
        share: 100,
      },
    ],
  },
  // Social links
  links: {
    website: "https://jarvis.ai",
    twitter: "https://twitter.com/jarvis_ai",
    discord: "https://discord.gg/jarvis",
    telegram: "https://t.me/jarvis_ai",
    github: "https://github.com/Matt-Aurora-Ventures/Jarvis",
  },
};

interface MetadataConfig {
  mintAddress: string;
  imageFile: string;
  keypairPath: string;
  network: "mainnet-beta" | "devnet";
}

async function setupTokenMetadata(config: MetadataConfig) {
  console.log("🚀 Starting Token Metadata Setup for $KR8TIV\n");

  // Load keypair
  const keypairData = JSON.parse(fs.readFileSync(config.keypairPath, "utf-8"));
  const keypair = Keypair.fromSecretKey(new Uint8Array(keypairData));
  console.log(`✅ Loaded keypair: ${keypair.publicKey.toBase58()}`);

  // Connect to Solana
  const connection = new Connection(
    config.network === "mainnet-beta"
      ? process.env.HELIUS_RPC_URL || clusterApiUrl("mainnet-beta")
      : clusterApiUrl("devnet"),
    "confirmed"
  );
  console.log(`✅ Connected to ${config.network}`);

  // Initialize Metaplex with Bundlr storage (Arweave)
  const metaplex = Metaplex.make(connection)
    .use(keypairIdentity(keypair))
    .use(
      bundlrStorage({
        address:
          config.network === "mainnet-beta"
            ? "https://node1.bundlr.network"
            : "https://devnet.bundlr.network",
        providerUrl:
          config.network === "mainnet-beta"
            ? process.env.HELIUS_RPC_URL || clusterApiUrl("mainnet-beta")
            : clusterApiUrl("devnet"),
        timeout: 60000,
      })
    );

  console.log("✅ Initialized Metaplex with Bundlr storage\n");

  // Step 1: Upload image to Arweave
  console.log("📤 Uploading token image to Arweave...");
  const imageBuffer = fs.readFileSync(config.imageFile);
  const imageFileName = path.basename(config.imageFile);
  const imageMetaplexFile = toMetaplexFile(imageBuffer, imageFileName);

  const imageUri = await metaplex.storage().upload(imageMetaplexFile);
  console.log(`✅ Image uploaded: ${imageUri}\n`);

  // Step 2: Create metadata JSON
  const metadata = {
    ...TOKEN_CONFIG,
    image: imageUri,
    properties: {
      ...TOKEN_CONFIG.properties,
      files: [{ uri: imageUri, type: "image/png" }],
      creators: [
        {
          address: keypair.publicKey.toBase58(),
          share: 100,
        },
      ],
    },
  };

  // Step 3: Upload metadata JSON
  console.log("📤 Uploading metadata JSON to Arweave...");
  const metadataUri = await metaplex.storage().uploadJson(metadata);
  console.log(`✅ Metadata uploaded: ${metadataUri}\n`);

  // Step 4: Create or update on-chain metadata
  const mintAddress = new PublicKey(config.mintAddress);

  try {
    // Check if metadata already exists
    const existingNft = await metaplex
      .nfts()
      .findByMint({ mintAddress })
      .catch(() => null);

    if (existingNft) {
      console.log("🔄 Updating existing metadata...");
      await metaplex.nfts().update({
        nftOrSft: existingNft,
        name: TOKEN_CONFIG.name,
        symbol: TOKEN_CONFIG.symbol,
        uri: metadataUri,
      });
      console.log("✅ Metadata updated successfully!\n");
    } else {
      console.log("🆕 Creating new metadata...");
      // For fungible tokens, use createSft
      await metaplex.nfts().createSft({
        uri: metadataUri,
        name: TOKEN_CONFIG.name,
        symbol: TOKEN_CONFIG.symbol,
        sellerFeeBasisPoints: 0,
        useExistingMint: mintAddress,
        mintAuthority: keypair,
        updateAuthority: keypair,
        tokenOwner: keypair.publicKey,
      });
      console.log("✅ Metadata created successfully!\n");
    }
  } catch (error) {
    console.error("❌ Error with metadata:", error);
    throw error;
  }

  // Step 5: Verify on explorers
  console.log("🔍 Verification Links:");
  console.log(
    `   Solscan: https://solscan.io/token/${config.mintAddress}${
      config.network === "devnet" ? "?cluster=devnet" : ""
    }`
  );
  console.log(
    `   Birdeye: https://birdeye.so/token/${config.mintAddress}?chain=solana`
  );
  console.log(
    `   Solana Explorer: https://explorer.solana.com/address/${config.mintAddress}${
      config.network === "devnet" ? "?cluster=devnet" : ""
    }`
  );

  console.log("\n✅ Token metadata setup complete!");

  return {
    mintAddress: config.mintAddress,
    imageUri,
    metadataUri,
    metadata,
  };
}

// Token Extensions Setup (for SPL Token 2022)
async function setupTokenExtensions(config: MetadataConfig) {
  console.log("\n🔧 Setting up Token Extensions (SPL Token 2022)...");

  // Token extensions that could be useful:
  const extensions = {
    // Transfer fees (if you want protocol fees on transfers)
    transferFee: {
      enabled: false,
      feeBasisPoints: 0, // 0% transfer fee
      maxFee: 0,
    },

    // Non-transferable (soulbound) - for governance tokens
    nonTransferable: false,

    // Interest-bearing (for staking representation)
    interestBearing: {
      enabled: false,
      rate: 0,
    },

    // Permanent delegate (for admin control)
    permanentDelegate: false,

    // Memo required on transfers
    memoRequired: false,

    // Confidential transfers (privacy)
    confidentialTransfer: false,
  };

  console.log("Token Extensions Configuration:");
  console.log(JSON.stringify(extensions, null, 2));
  console.log("\n✅ Token extensions configured (modify as needed)");

  return extensions;
}

// Verify token on Birdeye
async function verifyOnBirdeye(mintAddress: string) {
  console.log("\n🐦 Birdeye Verification Steps:");
  console.log("1. Go to https://birdeye.so/token-listing");
  console.log(`2. Enter mint address: ${mintAddress}`);
  console.log("3. Fill in token details:");
  console.log("   - Logo (upload same image)");
  console.log("   - Website: https://jarvis.ai");
  console.log("   - Twitter: @jarvis_ai");
  console.log("   - Discord: discord.gg/jarvis");
  console.log("4. Submit for review");
  console.log("\nNote: Verification may take 24-48 hours");
}

// Main execution
async function main() {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log("Usage: npx ts-node setup_metadata.ts <mint_address> <image_path> [keypair_path] [network]");
    console.log("\nExample:");
    console.log("  npx ts-node setup_metadata.ts 7K8..abc ./kr8tiv_logo.png ./keypair.json devnet");
    process.exit(1);
  }

  const config: MetadataConfig = {
    mintAddress: args[0],
    imageFile: args[1],
    keypairPath: args[2] || "./keypair.json",
    network: (args[3] as "mainnet-beta" | "devnet") || "devnet",
  };

  try {
    await setupTokenMetadata(config);
    await setupTokenExtensions(config);
    await verifyOnBirdeye(config.mintAddress);
  } catch (error) {
    console.error("❌ Setup failed:", error);
    process.exit(1);
  }
}

// Export for use as module
export {
  setupTokenMetadata,
  setupTokenExtensions,
  verifyOnBirdeye,
  TOKEN_CONFIG,
};

// Run if called directly
if (require.main === module) {
  main();
}
