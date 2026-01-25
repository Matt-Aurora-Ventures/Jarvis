#!/usr/bin/env node
/**
 * Update KR8TIV token metadata on-chain
 * Usage: node update_onchain.js <METADATA_IPFS_URL>
 */

const fs = require('fs');
const path = require('path');

// Config
const MINT = "7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf";
const KEYPAIR_PATH = path.join(__dirname, '..', 'keypair.json');

// Get metadata URL from command line
const metadataUrl = process.argv[2];

if (!metadataUrl) {
    console.error('Usage: node update_onchain.js <METADATA_IPFS_URL>');
    console.error('\nExample:');
    console.error('  node update_onchain.js https://ipfs.io/ipfs/bafkreic...');
    process.exit(1);
}

console.log('\n═══════════════════════════════════════════');
console.log('      KR8TIV On-Chain Metadata Update');
console.log('═══════════════════════════════════════════\n');

async function main() {
    try {
        // Load Metaplex SDK
        console.log('Loading Metaplex SDK...');
        const { createUmi } = require('@metaplex-foundation/umi-bundle-defaults');
        const { updateV1, fetchMetadataFromSeeds, mplTokenMetadata } = require('@metaplex-foundation/mpl-token-metadata');
        const { publicKey, keypairIdentity } = require('@metaplex-foundation/umi');

        // Load keypair
        console.log('Loading keypair...');
        const keypairData = JSON.parse(fs.readFileSync(KEYPAIR_PATH, 'utf8'));
        const keypairBytes = new Uint8Array(keypairData);

        // Create Umi
        console.log('Connecting to Solana mainnet...\n');
        const umi = createUmi('https://api.mainnet-beta.solana.com');
        umi.use(mplTokenMetadata());

        const signer = umi.eddsa.createKeypairFromSecretKey(keypairBytes);
        umi.use(keypairIdentity(signer));

        const mintPubkey = publicKey(MINT);

        // Fetch current
        console.log('Fetching current metadata...');
        const currentMetadata = await fetchMetadataFromSeeds(umi, { mint: mintPubkey });

        console.log(`\n  Current URI: ${currentMetadata.uri}`);
        console.log(`  New URI:     ${metadataUrl}\n`);

        // Confirm
        const readline = require('readline').createInterface({
            input: process.stdin,
            output: process.stdout
        });

        const answer = await new Promise(resolve => {
            readline.question('Update on-chain? (yes/no): ', resolve);
        });
        readline.close();

        if (answer.toLowerCase() !== 'yes') {
            console.log('\nCancelled.');
            process.exit(0);
        }

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

        const sigBase58 = Buffer.from(tx.signature).toString('base64');

        console.log('\n✓ SUCCESS! Metadata updated!\n');
        console.log(`Transaction: ${sigBase58}\n`);

        console.log('═══════════════════════════════════════════');
        console.log('              COMPLETE!');
        console.log('═══════════════════════════════════════════\n');
        console.log('Verify on Solscan:');
        console.log(`https://solscan.io/token/${MINT}\n`);

    } catch (error) {
        console.error('\n✗ Error:', error.message);
        if (error.logs) console.error('Logs:', error.logs);
        process.exit(1);
    }
}

main();
