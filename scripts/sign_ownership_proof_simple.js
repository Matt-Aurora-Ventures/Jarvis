#!/usr/bin/env node
/**
 * Generate wallet signature proof for bags.fm support ticket
 * This proves you own the creator wallet for the KR8TIV token
 */

const fs = require('fs');
const path = require('path');
const { Keypair } = require('@solana/web3.js');

const KEYPAIR_PATH = path.join(__dirname, '..', 'keypair.json');
const TOKEN_MINT = 'U1zc8QpnrQ3HBJUBrWFYWbQTLzNsCpPgZNegWXdBAGS';

async function generateProof() {
    console.log('═══════════════════════════════════════════');
    console.log('      KR8TIV Creator Ownership Proof');
    console.log('═══════════════════════════════════════════\n');

    // Load keypair
    const keypairData = JSON.parse(fs.readFileSync(KEYPAIR_PATH, 'utf8'));
    const keypair = Keypair.fromSecretKey(new Uint8Array(keypairData));

    const walletAddress = keypair.publicKey.toString();
    console.log('Wallet Address:', walletAddress);
    console.log('Token Mint:', TOKEN_MINT);
    console.log();

    // Create message to sign
    const timestamp = new Date().toISOString();
    const message = `I am the creator of KR8TIV token (${TOKEN_MINT}) and request metadata update.\nTimestamp: ${timestamp}`;

    console.log('Message to Sign:');
    console.log('─────────────────────────────────────────');
    console.log(message);
    console.log('─────────────────────────────────────────\n');

    // Sign the message using Keypair's sign method
    const messageBytes = Buffer.from(message, 'utf8');
    const signature = keypair.sign(messageBytes);
    const signatureBase58 = Buffer.from(signature).toString('base64');
    const signatureHex = Buffer.from(signature).toString('hex');

    console.log('Signature (Base64):');
    console.log(signatureBase58);
    console.log();
    console.log('Signature (Hex):');
    console.log(signatureHex);
    console.log();

    // Save to file
    const proofData = {
        walletAddress,
        tokenMint: TOKEN_MINT,
        message,
        timestamp,
        signatureBase64: signatureBase58,
        signatureHex,
        // Include public key for verification
        publicKey: walletAddress
    };

    const outputPath = path.join(__dirname, '..', 'ownership_proof.json');
    fs.writeFileSync(outputPath, JSON.stringify(proofData, null, 2));

    console.log('✓ Proof saved to:', outputPath);
    console.log();
    console.log('═══════════════════════════════════════════');
    console.log('         Copy to Support Ticket:');
    console.log('═══════════════════════════════════════════\n');
    console.log(`Creator Wallet Address: ${walletAddress}\n`);
    console.log(`Signed Message:\n${message}\n`);
    console.log(`Signature (Base64):\n${signatureBase58}\n`);
    console.log();
    console.log('Verification Instructions for bags.fm:');
    console.log('1. Verify this wallet address is the token creator');
    console.log('2. Verify the signature using Solana signature verification');
    console.log('3. Confirm the timestamp is recent');
    console.log();
}

generateProof().catch(console.error);
