#!/usr/bin/env node
/**
 * Check if KR8TIV token exists and has metadata
 */

const { Connection, PublicKey } = require('@solana/web3.js');

const MINT = "7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf";

async function main() {
    const connection = new Connection('https://api.mainnet-beta.solana.com');

    console.log('\nChecking token:', MINT);
    console.log('='.repeat(50));

    // Check if mint exists
    const mintPubkey = new PublicKey(MINT);
    const mintInfo = await connection.getAccountInfo(mintPubkey);

    if (!mintInfo) {
        console.log('✗ Token mint not found on mainnet');
        console.log('  May be on devnet or incorrect address');
        return;
    }

    console.log('✓ Token mint exists');
    console.log('  Owner:', mintInfo.owner.toString());
    console.log('  Data length:', mintInfo.data.length);

    // Derive Metaplex metadata PDA
    const METADATA_PROGRAM_ID = new PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s');

    const [metadataPDA] = PublicKey.findProgramAddressSync(
        [
            Buffer.from('metadata'),
            METADATA_PROGRAM_ID.toBuffer(),
            mintPubkey.toBuffer(),
        ],
        METADATA_PROGRAM_ID
    );

    console.log('\nMetaplex Metadata PDA:', metadataPDA.toString());

    const metadataInfo = await connection.getAccountInfo(metadataPDA);

    if (!metadataInfo) {
        console.log('✗ No Metaplex metadata found');
        console.log('\nThis token may have been created with:');
        console.log('  - bags.fm custom metadata');
        console.log('  - Token-2022 program');
        console.log('  - Or no metadata at all');
        console.log('\nTo add metadata, you need to create it first.');
        return;
    }

    console.log('✓ Metaplex metadata exists');
    console.log('  Data length:', metadataInfo.data.length);
}

main().catch(console.error);
