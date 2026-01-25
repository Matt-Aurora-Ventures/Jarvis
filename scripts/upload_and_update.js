#!/usr/bin/env node
/**
 * Simple KR8TIV Metadata Updater
 * Uses NFT.Storage API + Metaplex Umi
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

const MINT = "7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf";
const LOGO_PATH = path.join(__dirname, '..', 'assets', 'kr8tiv', 'logo.png');
const KEYPAIR_PATH = path.join(__dirname, '..', 'keypair.json');
const NFT_STORAGE_API_KEY = "08c145c0.2313919737a346fa8ac2d8091d24b34b";

console.log('\n═══════════════════════════════════════════');
console.log('        KR8TIV Metadata Update');
console.log('═══════════════════════════════════════════\n');

// Upload file to NFT.Storage using curl
async function uploadToIPFS(filePath, filename) {
    console.log(`Uploading ${filename}...`);

    const cmd = `curl -X POST https://api.nft.storage/upload ` +
                `-H "Authorization: Bearer ${NFT_STORAGE_API_KEY}" ` +
                `-H "Content-Type: application/octet-stream" ` +
                `--data-binary "@${filePath}"`;

    try {
        const { stdout } = await execAsync(cmd);
        const response = JSON.parse(stdout);

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.error?.message || 'Unknown error'}`);
        }

        const ipfsUrl = `https://ipfs.io/ipfs/${response.value.cid}`;
        console.log(`✓ ${filename} uploaded: ${ipfsUrl}\n`);
        return ipfsUrl;
    } catch (error) {
        throw new Error(`Failed to upload ${filename}: ${error.message}`);
    }
}

async function main() {
    try {
        // Step 1: Upload logo
        console.log('[1/3] Uploading logo to IPFS...\n');
        const imageUrl = await uploadToIPFS(LOGO_PATH, 'logo.png');

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

        const metadataPath = path.join(__dirname, '..', 'assets', 'kr8tiv', 'metadata_upload.json');
        fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));

        const metadataUrl = await uploadToIPFS(metadataPath, 'metadata.json');

        // Step 3: Update on-chain
        console.log('[3/3] Updating on-chain metadata...\n');
        console.log('Review:');
        console.log('═══════════════════════════════════════════');
        console.log(`  Mint:     ${MINT}`);
        console.log(`  Image:    ${imageUrl}`);
        console.log(`  Metadata: ${metadataUrl}`);
        console.log('═══════════════════════════════════════════\n');

        // Load Metaplex packages
        const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
        const { updateV1, fetchMetadataFromSeeds, mplTokenMetadata } = require('@metaplex-foundation/mpl-token-metadata');
        const { publicKey, keypairIdentity } = require('@metaplex-foundation/umi');

        // Load keypair
        const keypairData = JSON.parse(fs.readFileSync(KEYPAIR_PATH, 'utf8'));
        const keypairBytes = new Uint8Array(keypairData);

        // Create Umi instance
        console.log('Connecting to Solana...');
        const umi = createUmi('https://api.mainnet-beta.solana.com');
        umi.use(mplTokenMetadata());

        // Set keypair
        const signer = umi.eddsa.createKeypairFromSecretKey(keypairBytes);
        umi.use(keypairIdentity(signer));

        const mintPubkey = publicKey(MINT);

        // Fetch current metadata
        console.log('Fetching current metadata...');
        const currentMetadata = await fetchMetadataFromSeeds(umi, { mint: mintPubkey });

        console.log(`Current URI: ${currentMetadata.uri}`);
        console.log(`New URI: ${metadataUrl}`);

        // Update
        console.log('\nSending update transaction...');

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

        console.log('\n✓ SUCCESS! Metadata updated on-chain!\n');
        console.log(`Transaction signature: ${Buffer.from(tx.signature).toString('base64')}`);

        console.log('\n═══════════════════════════════════════════');
        console.log('              COMPLETE!');
        console.log('═══════════════════════════════════════════\n');
        console.log('Verify on Solscan:');
        console.log(`https://solscan.io/token/${MINT}\n`);
        console.log('Look for:');
        console.log('  ✓ Blue energy wave KR8TIV logo');
        console.log('  ✓ Name: KR8TIV');
        console.log('  ✓ Description showing');
        console.log('  ✓ Website links\n');

    } catch (error) {
        console.error('\n✗ Error:', error.message);
        console.error(error.stack);
        process.exit(1);
    }
}

main();
