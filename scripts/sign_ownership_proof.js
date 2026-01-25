#!/usr/bin/env node
/**
 * Generate wallet signature proof for bags.fm support ticket
 * This proves you own the creator wallet for the KR8TIV token
 */

const fs = require('fs');
const path = require('path');
const { Keypair } = require('@solana/web3.js');
const { sign } = require('@solana/web3.js/node_modules/tweetnacl');

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

    // Sign the message
    const messageBytes = Buffer.from(message, 'utf8');
    const signature = nacl.sign.detached(messageBytes, keypair.secretKey);
    const signatureBase58 = Buffer.from(signature).toString('base64');

    console.log('Signature (Base64):');
    console.log(signatureBase58);
    console.log();

    // Save to file
    const proofData = {
        walletAddress,
        tokenMint: TOKEN_MINT,
        message,
        timestamp,
        signature: signatureBase58,
        signatureHex: Buffer.from(signature).toString('hex')
    };

    const outputPath = path.join(__dirname, '..', 'ownership_proof.json');
    fs.writeFileSync(outputPath, JSON.stringify(proofData, null, 2));

    console.log('✓ Proof saved to:', outputPath);
    console.log();
    console.log('═══════════════════════════════════════════');
    console.log('Copy this information to your support ticket:');
    console.log('═══════════════════════════════════════════\n');
    console.log(`Wallet Address: ${walletAddress}`);
    console.log(`Token Mint: ${TOKEN_MINT}`);
    console.log(`Message: ${message}`);
    console.log(`Signature: ${signatureBase58}`);
    console.log();
}

generateProof().catch(console.error);
