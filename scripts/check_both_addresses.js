#!/usr/bin/env node
const { Connection, PublicKey } = require('@solana/web3.js');

const addresses = {
    'Mint (you said)': '7BLHKsHRGJsTKQdZYaC3tRDeUChJ9E2XsMPpg2Tv23cf',
    'Contract (you said)': 'U1zc8QpnrQ3HBJUBrWFYWbQTLzNsCpPgZNegWXdBAGS'
};

async function checkAddress(label, address) {
    const connection = new Connection('https://api.mainnet-beta.solana.com');

    console.log(`\n${'='.repeat(60)}`);
    console.log(`Checking ${label}:`);
    console.log(`Address: ${address}`);
    console.log('='.repeat(60));

    try {
        const pubkey = new PublicKey(address);
        const info = await connection.getAccountInfo(pubkey);

        if (!info) {
            console.log('✗ Not found on mainnet');
            return null;
        }

        console.log('✓ Found on mainnet!');
        console.log(`  Owner: ${info.owner.toString()}`);
        console.log(`  Data length: ${info.data.length} bytes`);

        // Check if it's a token mint
        if (info.owner.toString() === 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA') {
            console.log('  Type: SPL Token Mint');
        } else if (info.owner.toString() === 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb') {
            console.log('  Type: Token-2022 Mint');
        } else {
            console.log(`  Type: Program owned by ${info.owner.toString()}`);
        }

        return info;
    } catch (e) {
        console.log(`✗ Invalid address: ${e.message}`);
        return null;
    }
}

async function main() {
    for (const [label, address] of Object.entries(addresses)) {
        await checkAddress(label, address);
    }

    console.log('\n' + '='.repeat(60));
    console.log('Recommendation:');
    console.log('='.repeat(60));
    console.log('Please check Solscan or bags.fm to confirm the correct mint address.');
    console.log('The token may be:');
    console.log('  - On devnet (not mainnet)');
    console.log('  - Not yet created');
    console.log('  - At a different address');
}

main().catch(console.error);
