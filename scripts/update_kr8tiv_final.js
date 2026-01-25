#!/usr/bin/env node
/**
 * KR8TIV Metadata Updater - Pure Node.js
 * No external dependencies needed
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const MINT = "7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf";
const LOGO_PATH = path.join(__dirname, '..', 'assets', 'kr8tiv', 'logo.png');
const KEYPAIR_PATH = path.join(__dirname, '..', 'keypair.json');
const NFT_STORAGE_API_KEY = "08c145c0.2313919737a346fa8ac2d8091d24b34b";

console.log('\n═══════════════════════════════════════════');
console.log('        KR8TIV Metadata Update');
console.log('═══════════════════════════════════════════\n');

// Upload using fetch (Node 18+)
async function uploadFile(filePath, filename) {
    console.log(`Uploading ${filename}...`);

    const fileBuffer = fs.readFileSync(filePath);
    const blob = new Blob([fileBuffer]);

    const formData = new FormData();
    formData.append('file', blob, filename);

    const response = await fetch('https://api.nft.storage/upload', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${NFT_STORAGE_API_KEY}`,
        },
        body: formData,
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Upload failed: ${error}`);
    }

    const data = await response.json();
    const ipfsUrl = `https://ipfs.io/ipfs/${data.value.cid}`;
    console.log(`✓ ${filename} uploaded\n  ${ipfsUrl}\n`);
    return ipfsUrl;
}

async function uploadJSON(jsonData, name) {
    console.log(`Uploading ${name}...`);

    const blob = new Blob([JSON.stringify(jsonData)], { type: 'application/json' });
    const formData = new FormData();
    formData.append('file', blob, name);

    const response = await fetch('https://api.nft.storage/upload', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${NFT_STORAGE_API_KEY}`,
        },
        body: formData,
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Upload failed: ${error}`);
    }

    const data = await response.json();
    const ipfsUrl = `https://ipfs.io/ipfs/${data.value.cid}`;
    console.log(`✓ ${name} uploaded\n  ${ipfsUrl}\n`);
    return ipfsUrl;
}

async function main() {
    try {
        // Step 1: Upload logo
        console.log('[1/3] Uploading logo to IPFS...\n');
        const imageUrl = await uploadFile(LOGO_PATH, 'kr8tiv-logo.png');

        // Step 2: Create and upload metadata
        console.log('[2/3] Creating and uploading metadata...\n');

        const metadata = {
            name: "KR8TIV",
            symbol: "KR8TIV",
            description: "kr8tiv builds Decentralized Open Sourced AI for the masses — powerful, practical, and dangerous (in a good way).",
            image: imageUrl,
            external_url: "https://kr8tiv.ai",
            attributes: [
                { trait_type: "Category", value: "AI" },
                { trait_type: "Type", value: "Utility Token" },
                { trait_type: "Network", value: "Solana" },
                { trait_type: "Platform", value: "Decentralized AI" }
            ],
            properties: {
                files: [{ uri: imageUrl, type: "image/png" }],
                category: "image",
                creators: []
            },
            links: {
                website: "https://kr8tiv.ai",
                jarvis: "https://jarvislife.io",
                twitter: "https://x.com/kr8tivai",
                jarvis_twitter: "https://x.com/Jarvis_lifeos"
            }
        };

        const metadataUrl = await uploadJSON(metadata, 'metadata.json');

        // Step 3: Update on-chain
        console.log('[3/3] Updating on-chain metadata...\n');
        console.log('Review:');
        console.log('═══════════════════════════════════════════');
        console.log(`  Mint:     ${MINT}`);
        console.log(`  Image:    ${imageUrl}`);
        console.log(`  Metadata: ${metadataUrl}`);
        console.log('═══════════════════════════════════════════\n');

        // Load Metaplex SDK
        const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
        const { updateV1, fetchMetadataFromSeeds, mplTokenMetadata } = require('@metaplex-foundation/mpl-token-metadata');
        const { publicKey, keypairIdentity } = require('@metaplex-foundation/umi');

        // Load keypair
        const keypairData = JSON.parse(fs.readFileSync(KEYPAIR_PATH, 'utf8'));
        const keypairBytes = new Uint8Array(keypairData);

        // Create Umi
        console.log('Connecting to Solana mainnet...');
        const umi = createUmi('https://api.mainnet-beta.solana.com');
        umi.use(mplTokenMetadata());

        const signer = umi.eddsa.createKeypairFromSecretKey(keypairBytes);
        umi.use(keypairIdentity(signer));

        const mintPubkey = publicKey(MINT);

        // Fetch current
        console.log('Fetching current metadata...');
        const currentMetadata = await fetchMetadataFromSeeds(umi, { mint: mintPubkey });

        console.log(`  Old URI: ${currentMetadata.uri}`);
        console.log(`  New URI: ${metadataUrl}\n`);

        // Update
        console.log('Sending update transaction...');

        const tx = await updateV1(umi, {
            mint: mintPubkey,
            authority: signer,
            data: {
                name: currentMetadata.name,
                symbol: currentMetadata.symbol,
                uri: metadataUrl,
                sellerFeeBasisPoints: currentMetadata.sellerFeeBasisPoints,
                creators: currentMetadata.creators,
            },
        }).sendAndConfirm(umi);

        const sigBase58 = Buffer.from(tx.signature).toString('base64');

        console.log('\n✓ SUCCESS! Metadata updated!\n');
        console.log(`Signature: ${sigBase58}\n`);

        console.log('═══════════════════════════════════════════');
        console.log('              COMPLETE!');
        console.log('═══════════════════════════════════════════\n');
        console.log('Verify on Solscan:');
        console.log(`https://solscan.io/token/${MINT}\n`);
        console.log('Look for:');
        console.log('  ✓ Blue energy wave KR8TIV logo');
        console.log('  ✓ Name: KR8TIV');
        console.log('  ✓ Symbol: KR8TIV');
        console.log('  ✓ Description visible');
        console.log('  ✓ Links working\n');

        // Save URLs for reference
        const urlsPath = path.join(__dirname, '..', 'assets', 'kr8tiv', 'ipfs_urls.json');
        fs.writeFileSync(urlsPath, JSON.stringify({
            imageUrl,
            metadataUrl,
            transaction: sigBase58,
            timestamp: new Date().toISOString(),
        }, null, 2));

        console.log(`URLs saved to: ${urlsPath}\n`);

    } catch (error) {
        console.error('\n✗ Error:', error.message);
        if (error.stack) console.error(error.stack);
        process.exit(1);
    }
}

main();
