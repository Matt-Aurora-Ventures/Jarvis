#!/usr/bin/env node
/**
 * KR8TIV Token Metadata Updater (Node.js version)
 * Uses Metaplex Umi SDK - no Rust/cargo required!
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

// Configuration
const MINT = "7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf";
const LOGO_PATH = path.join(__dirname, '..', 'assets', 'kr8tiv', 'logo.png');
const KEYPAIR_PATH = path.join(__dirname, '..', 'keypair.json');
const NFT_STORAGE_API_KEY = process.env.NFT_STORAGE_API_KEY || "08c145c0.2313919737a346fa8ac2d8091d24b34b";

console.log('\n════════════════════════════════════════════════════════');
console.log('          KR8TIV Metadata Updater (Node.js)');
console.log('════════════════════════════════════════════════════════\n');

// Step 1: Check dependencies
console.log('[1/5] Checking dependencies...\n');

const requiredPackages = [
    '@metaplex-foundation/umi',
    '@metaplex-foundation/umi-bundle-defaults',
    '@metaplex-foundation/mpl-token-metadata',
];

let needsInstall = false;
for (const pkg of requiredPackages) {
    try {
        require.resolve(pkg);
        console.log(`✓ ${pkg}`);
    } catch (e) {
        console.log(`✗ ${pkg} (will install)`);
        needsInstall = true;
    }
}

if (needsInstall) {
    console.log('\nInstalling required packages...');
    const { execSync } = require('child_process');
    execSync(`npm install ${requiredPackages.join(' ')}`, { stdio: 'inherit' });
}

// Step 2: Upload logo to NFT.Storage
async function uploadToNFTStorage(filePath) {
    console.log('\n[2/5] Uploading logo to NFT.Storage...\n');

    const FormData = require('form-data');
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));

    return new Promise((resolve, reject) => {
        const options = {
            hostname: 'api.nft.storage',
            path: '/upload',
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${NFT_STORAGE_API_KEY}`,
                ...form.getHeaders(),
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                if (res.statusCode === 200) {
                    const response = JSON.parse(data);
                    const ipfsUrl = `https://ipfs.io/ipfs/${response.value.cid}`;
                    console.log(`✓ Logo uploaded: ${ipfsUrl}`);
                    resolve(ipfsUrl);
                } else {
                    reject(new Error(`Upload failed: ${data}`));
                }
            });
        });

        req.on('error', reject);
        form.pipe(req);
    });
}

// Step 3: Create and upload metadata
async function uploadMetadata(imageUrl) {
    console.log('\n[3/5] Creating and uploading metadata...\n');

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

    const metadataBlob = Buffer.from(JSON.stringify(metadata));

    return new Promise((resolve, reject) => {
        const options = {
            hostname: 'api.nft.storage',
            path: '/upload',
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${NFT_STORAGE_API_KEY}`,
                'Content-Type': 'application/json',
                'Content-Length': metadataBlob.length,
            },
        };

        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                if (res.statusCode === 200) {
                    const response = JSON.parse(data);
                    const metadataUrl = `https://ipfs.io/ipfs/${response.value.cid}`;
                    console.log(`✓ Metadata uploaded: ${metadataUrl}`);
                    resolve(metadataUrl);
                } else {
                    reject(new Error(`Upload failed: ${data}`));
                }
            });
        });

        req.on('error', reject);
        req.write(metadataBlob);
        req.end();
    });
}

// Step 4: Update on-chain with Metaplex Umi
async function updateOnChain(metadataUrl) {
    console.log('\n[4/5] Updating on-chain metadata...\n');

    const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
    const { updateV1, fetchMetadataFromSeeds } = require('@metaplex-foundation/mpl-token-metadata');
    const { publicKey, keypairIdentity, transactionBuilder } = require('@metaplex-foundation/umi');

    // Load keypair
    const keypairData = JSON.parse(fs.readFileSync(KEYPAIR_PATH, 'utf8'));
    const keypairBytes = new Uint8Array(keypairData);

    // Create Umi instance
    const umi = createUmi('https://api.mainnet-beta.solana.com');

    // Set keypair as signer
    const signer = umi.eddsa.createKeypairFromSecretKey(keypairBytes);
    umi.use(keypairIdentity(signer));

    const mintPubkey = publicKey(MINT);

    // Fetch current metadata
    console.log('Fetching current metadata...');
    const currentMetadata = await fetchMetadataFromSeeds(umi, { mint: mintPubkey });

    console.log(`Current URI: ${currentMetadata.uri}`);
    console.log(`New URI: ${metadataUrl}`);

    // Update metadata
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

    console.log(`✓ Transaction confirmed!`);
    console.log(`  Signature: ${Buffer.from(tx.signature).toString('base64')}`);

    return tx;
}

// Step 5: Optionally freeze metadata
async function freezeMetadata() {
    console.log('\n[5/5] Freeze metadata (optional)...\n');

    const readline = require('readline').createInterface({
        input: process.stdin,
        output: process.stdout
    });

    return new Promise((resolve) => {
        readline.question('Freeze metadata permanently? (yes/no): ', async (answer) => {
            readline.close();

            if (answer.toLowerCase() !== 'yes') {
                console.log('\nSkipped freeze.');
                resolve(false);
                return;
            }

            console.log('\n⚠️  WARNING: This is PERMANENT and IRREVERSIBLE');
            console.log('Type "FREEZE" to confirm: ');

            const readline2 = require('readline').createInterface({
                input: process.stdin,
                output: process.stdout
            });

            readline2.question('', async (confirm) => {
                readline2.close();

                if (confirm !== 'FREEZE') {
                    console.log('\nFreeze cancelled.');
                    resolve(false);
                    return;
                }

                console.log('\nFreezing metadata...');

                const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
                const { updateV1, fetchMetadataFromSeeds } = require('@metaplex-foundation/mpl-token-metadata');
                const { publicKey, keypairIdentity } = require('@metaplex-foundation/umi');

                const keypairData = JSON.parse(fs.readFileSync(KEYPAIR_PATH, 'utf8'));
                const keypairBytes = new Uint8Array(keypairData);
                const umi = createUmi('https://api.mainnet-beta.solana.com');
                const signer = umi.eddsa.createKeypairFromSecretKey(keypairBytes);
                umi.use(keypairIdentity(signer));

                const tx = await updateV1(umi, {
                    mint: publicKey(MINT),
                    authority: signer,
                    newUpdateAuthority: null,
                    isMutable: false,
                }).sendAndConfirm(umi);

                console.log('\n✓ METADATA IS NOW IMMUTABLE!');
                console.log(`  Signature: ${Buffer.from(tx.signature).toString('base64')}`);
                resolve(true);
            });
        });
    });
}

// Main execution
async function main() {
    try {
        // Upload logo
        const imageUrl = await uploadToNFTStorage(LOGO_PATH);

        // Create and upload metadata
        const metadataUrl = await uploadMetadata(imageUrl);

        // Update on-chain
        await updateOnChain(metadataUrl);

        // Freeze (optional)
        await freezeMetadata();

        console.log('\n════════════════════════════════════════════════════════');
        console.log('                    SUCCESS!');
        console.log('════════════════════════════════════════════════════════\n');
        console.log('Verify on Solscan:');
        console.log(`https://solscan.io/token/${MINT}\n`);

    } catch (error) {
        console.error('\n✗ Error:', error.message);
        process.exit(1);
    }
}

main();
