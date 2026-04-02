/**
 * Transaction Builder UI
 * Prompt #47: Visual transaction builder with preview and simulation
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  AlertCircle,
  ArrowRight,
  Check,
  Loader2,
  Plus,
  Trash2,
  Eye,
  Send,
  Wallet,
  Coins,
  ArrowDownUp,
  Lock
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface Instruction {
  id: string;
  type: InstructionType;
  params: Record<string, any>;
  programId: string;
  accounts: AccountMeta[];
  data: string;
}

interface AccountMeta {
  pubkey: string;
  isSigner: boolean;
  isWritable: boolean;
}

interface TransactionPreview {
  instructions: Instruction[];
  estimatedFee: number;
  computeUnits: number;
  signers: string[];
  simulationResult?: SimulationResult;
}

interface SimulationResult {
  success: boolean;
  logs: string[];
  unitsConsumed: number;
  error?: string;
  balanceChanges: BalanceChange[];
}

interface BalanceChange {
  account: string;
  token: string;
  before: number;
  after: number;
  change: number;
}

type InstructionType =
  | 'stake'
  | 'unstake'
  | 'claim'
  | 'swap'
  | 'transfer'
  | 'delegate'
  | 'vote';

// =============================================================================
// INSTRUCTION TEMPLATES
// =============================================================================

const INSTRUCTION_TEMPLATES: Record<InstructionType, {
  name: string;
  icon: React.ElementType;
  description: string;
  fields: {
    name: string;
    type: 'text' | 'number' | 'select' | 'pubkey';
    label: string;
    placeholder?: string;
    options?: { value: string; label: string }[];
    required?: boolean;
  }[];
}> = {
  stake: {
    name: 'Stake Tokens',
    icon: Lock,
    description: 'Stake $KR8TIV tokens to earn rewards',
    fields: [
      { name: 'amount', type: 'number', label: 'Amount', placeholder: '1000', required: true },
      { name: 'lockDuration', type: 'select', label: 'Lock Duration', options: [
        { value: '30', label: '30 Days (1.2x)' },
        { value: '90', label: '90 Days (1.5x)' },
        { value: '180', label: '180 Days (2.0x)' },
        { value: '365', label: '365 Days (2.5x)' }
      ], required: true }
    ]
  },
  unstake: {
    name: 'Unstake Tokens',
    icon: Lock,
    description: 'Unstake tokens and claim rewards',
    fields: [
      { name: 'amount', type: 'number', label: 'Amount', placeholder: 'Amount to unstake', required: true },
      { name: 'claimRewards', type: 'select', label: 'Claim Rewards', options: [
        { value: 'true', label: 'Yes - Claim with unstake' },
        { value: 'false', label: 'No - Leave rewards' }
      ], required: true }
    ]
  },
  claim: {
    name: 'Claim Rewards',
    icon: Coins,
    description: 'Claim pending staking rewards',
    fields: []
  },
  swap: {
    name: 'Swap Tokens',
    icon: ArrowDownUp,
    description: 'Swap tokens via JARVIS routing',
    fields: [
      { name: 'inputMint', type: 'pubkey', label: 'Input Token', placeholder: 'Token mint address', required: true },
      { name: 'outputMint', type: 'pubkey', label: 'Output Token', placeholder: 'Token mint address', required: true },
      { name: 'amount', type: 'number', label: 'Amount', placeholder: 'Amount to swap', required: true },
      { name: 'slippage', type: 'select', label: 'Max Slippage', options: [
        { value: '50', label: '0.5%' },
        { value: '100', label: '1.0%' },
        { value: '200', label: '2.0%' },
        { value: '500', label: '5.0%' }
      ], required: true }
    ]
  },
  transfer: {
    name: 'Transfer Tokens',
    icon: Send,
    description: 'Transfer tokens to another wallet',
    fields: [
      { name: 'recipient', type: 'pubkey', label: 'Recipient', placeholder: 'Wallet address', required: true },
      { name: 'mint', type: 'pubkey', label: 'Token Mint', placeholder: 'Token mint (empty for SOL)', required: false },
      { name: 'amount', type: 'number', label: 'Amount', placeholder: 'Amount to send', required: true }
    ]
  },
  delegate: {
    name: 'Delegate Voting Power',
    icon: Wallet,
    description: 'Delegate governance voting power',
    fields: [
      { name: 'delegate', type: 'pubkey', label: 'Delegate To', placeholder: 'Wallet address', required: true }
    ]
  },
  vote: {
    name: 'Cast Vote',
    icon: Check,
    description: 'Vote on a governance proposal',
    fields: [
      { name: 'proposalId', type: 'text', label: 'Proposal ID', placeholder: 'Proposal identifier', required: true },
      { name: 'voteType', type: 'select', label: 'Vote', options: [
        { value: 'for', label: 'For' },
        { value: 'against', label: 'Against' },
        { value: 'abstain', label: 'Abstain' }
      ], required: true }
    ]
  }
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function TransactionBuilder() {
  const [instructions, setInstructions] = useState<Instruction[]>([]);
  const [preview, setPreview] = useState<TransactionPreview | null>(null);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Add instruction
  const addInstruction = useCallback((type: InstructionType) => {
    const template = INSTRUCTION_TEMPLATES[type];
    const newInstruction: Instruction = {
      id: `ix-${Date.now()}`,
      type,
      params: {},
      programId: '',
      accounts: [],
      data: ''
    };

    // Initialize default values
    template.fields.forEach(field => {
      if (field.options?.length) {
        newInstruction.params[field.name] = field.options[0].value;
      }
    });

    setInstructions(prev => [...prev, newInstruction]);
    setPreview(null);
    setSimulation(null);
  }, []);

  // Remove instruction
  const removeInstruction = useCallback((id: string) => {
    setInstructions(prev => prev.filter(ix => ix.id !== id));
    setPreview(null);
    setSimulation(null);
  }, []);

  // Update instruction params
  const updateInstructionParam = useCallback((id: string, param: string, value: any) => {
    setInstructions(prev => prev.map(ix => {
      if (ix.id !== id) return ix;
      return {
        ...ix,
        params: { ...ix.params, [param]: value }
      };
    }));
    setPreview(null);
    setSimulation(null);
  }, []);

  // Build transaction preview
  const buildPreview = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch('/api/transaction/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instructions })
      });

      if (!response.ok) throw new Error('Failed to build preview');

      const previewData = await response.json();
      setPreview(previewData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to build transaction');
    }
  }, [instructions]);

  // Simulate transaction
  const simulateTransaction = useCallback(async () => {
    if (!preview) return;

    setIsSimulating(true);
    setError(null);

    try {
      const response = await fetch('/api/transaction/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instructions })
      });

      if (!response.ok) throw new Error('Simulation failed');

      const result = await response.json();
      setSimulation(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setIsSimulating(false);
    }
  }, [preview, instructions]);

  // Send transaction
  const sendTransaction = useCallback(async () => {
    if (!simulation?.success) return;

    setIsSending(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch('/api/transaction/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instructions })
      });

      if (!response.ok) throw new Error('Transaction failed');

      const result = await response.json();
      setSuccess(`Transaction confirmed: ${result.signature}`);
      setInstructions([]);
      setPreview(null);
      setSimulation(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Transaction failed');
    } finally {
      setIsSending(false);
    }
  }, [simulation, instructions]);

  // Move instruction up/down
  const moveInstruction = useCallback((id: string, direction: 'up' | 'down') => {
    setInstructions(prev => {
      const idx = prev.findIndex(ix => ix.id === id);
      if (idx === -1) return prev;

      const newIdx = direction === 'up' ? idx - 1 : idx + 1;
      if (newIdx < 0 || newIdx >= prev.length) return prev;

      const newInstructions = [...prev];
      [newInstructions[idx], newInstructions[newIdx]] = [newInstructions[newIdx], newInstructions[idx]];
      return newInstructions;
    });
    setPreview(null);
    setSimulation(null);
  }, []);

  return (
    <div className="space-y-6 max-w-4xl mx-auto p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Transaction Builder</h1>
        <p className="text-muted-foreground">
          Build, preview, and simulate transactions before sending
        </p>
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert className="border-green-500 bg-green-50">
          <Check className="h-4 w-4 text-green-500" />
          <AlertDescription className="text-green-700">{success}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Instruction Palette */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Add Instruction</CardTitle>
            <CardDescription>Click to add to transaction</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.entries(INSTRUCTION_TEMPLATES).map(([type, template]) => {
              const Icon = template.icon;
              return (
                <Button
                  key={type}
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => addInstruction(type as InstructionType)}
                >
                  <Icon className="h-4 w-4 mr-2" />
                  {template.name}
                </Button>
              );
            })}
          </CardContent>
        </Card>

        {/* Instruction List */}
        <div className="lg:col-span-2 space-y-4">
          {instructions.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center text-muted-foreground">
                <Plus className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No instructions yet</p>
                <p className="text-sm">Add instructions from the palette</p>
              </CardContent>
            </Card>
          ) : (
            <>
              {instructions.map((instruction, index) => {
                const template = INSTRUCTION_TEMPLATES[instruction.type];
                const Icon = template.icon;

                return (
                  <Card key={instruction.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{index + 1}</Badge>
                          <Icon className="h-4 w-4" />
                          <CardTitle className="text-base">{template.name}</CardTitle>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => moveInstruction(instruction.id, 'up')}
                            disabled={index === 0}
                          >
                            ↑
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => moveInstruction(instruction.id, 'down')}
                            disabled={index === instructions.length - 1}
                          >
                            ↓
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeInstruction(instruction.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </div>
                      <CardDescription>{template.description}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {template.fields.map(field => (
                        <div key={field.name} className="space-y-2">
                          <Label htmlFor={`${instruction.id}-${field.name}`}>
                            {field.label}
                            {field.required && <span className="text-destructive ml-1">*</span>}
                          </Label>
                          {field.type === 'select' ? (
                            <Select
                              value={instruction.params[field.name] || ''}
                              onValueChange={(value) =>
                                updateInstructionParam(instruction.id, field.name, value)
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder={`Select ${field.label.toLowerCase()}`} />
                              </SelectTrigger>
                              <SelectContent>
                                {field.options?.map(option => (
                                  <SelectItem key={option.value} value={option.value}>
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <Input
                              id={`${instruction.id}-${field.name}`}
                              type={field.type === 'number' ? 'number' : 'text'}
                              placeholder={field.placeholder}
                              value={instruction.params[field.name] || ''}
                              onChange={(e) =>
                                updateInstructionParam(instruction.id, field.name, e.target.value)
                              }
                            />
                          )}
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                );
              })}

              {/* Action Buttons */}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={buildPreview}
                  disabled={instructions.length === 0}
                >
                  <Eye className="h-4 w-4 mr-2" />
                  Preview
                </Button>
                <Button
                  variant="outline"
                  onClick={simulateTransaction}
                  disabled={!preview || isSimulating}
                >
                  {isSimulating ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Check className="h-4 w-4 mr-2" />
                  )}
                  Simulate
                </Button>
                <Button
                  onClick={sendTransaction}
                  disabled={!simulation?.success || isSending}
                >
                  {isSending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4 mr-2" />
                  )}
                  Send Transaction
                </Button>
              </div>
            </>
          )}

          {/* Preview & Simulation Results */}
          {(preview || simulation) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Transaction Details</CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="preview">
                  <TabsList>
                    <TabsTrigger value="preview">Preview</TabsTrigger>
                    {simulation && <TabsTrigger value="simulation">Simulation</TabsTrigger>}
                  </TabsList>

                  <TabsContent value="preview" className="space-y-4 mt-4">
                    {preview && (
                      <>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label className="text-muted-foreground">Estimated Fee</Label>
                            <p className="text-lg font-medium">
                              {(preview.estimatedFee / 1e9).toFixed(6)} SOL
                            </p>
                          </div>
                          <div>
                            <Label className="text-muted-foreground">Compute Units</Label>
                            <p className="text-lg font-medium">
                              {preview.computeUnits.toLocaleString()}
                            </p>
                          </div>
                        </div>

                        <div>
                          <Label className="text-muted-foreground">Required Signers</Label>
                          <div className="mt-1 space-y-1">
                            {preview.signers.map((signer, i) => (
                              <div key={i} className="flex items-center gap-2">
                                <Wallet className="h-4 w-4" />
                                <code className="text-sm">{signer}</code>
                              </div>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </TabsContent>

                  {simulation && (
                    <TabsContent value="simulation" className="space-y-4 mt-4">
                      <div className="flex items-center gap-2">
                        {simulation.success ? (
                          <>
                            <Check className="h-5 w-5 text-green-500" />
                            <span className="text-green-600 font-medium">
                              Simulation Successful
                            </span>
                          </>
                        ) : (
                          <>
                            <AlertCircle className="h-5 w-5 text-destructive" />
                            <span className="text-destructive font-medium">
                              Simulation Failed
                            </span>
                          </>
                        )}
                      </div>

                      {simulation.error && (
                        <Alert variant="destructive">
                          <AlertDescription>{simulation.error}</AlertDescription>
                        </Alert>
                      )}

                      <div>
                        <Label className="text-muted-foreground">Compute Units Used</Label>
                        <p>{simulation.unitsConsumed.toLocaleString()}</p>
                      </div>

                      {simulation.balanceChanges.length > 0 && (
                        <div>
                          <Label className="text-muted-foreground">Balance Changes</Label>
                          <div className="mt-2 space-y-2">
                            {simulation.balanceChanges.map((change, i) => (
                              <div
                                key={i}
                                className="flex items-center justify-between p-2 bg-muted rounded"
                              >
                                <div>
                                  <code className="text-sm">{change.account.slice(0, 8)}...</code>
                                  <span className="text-muted-foreground text-sm ml-2">
                                    ({change.token})
                                  </span>
                                </div>
                                <span className={
                                  change.change > 0 ? 'text-green-600' : 'text-red-600'
                                }>
                                  {change.change > 0 ? '+' : ''}{change.change}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {simulation.logs.length > 0 && (
                        <div>
                          <Label className="text-muted-foreground">Transaction Logs</Label>
                          <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-x-auto max-h-48">
                            {simulation.logs.join('\n')}
                          </pre>
                        </div>
                      )}
                    </TabsContent>
                  )}
                </Tabs>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// API ROUTES (Python/FastAPI)
// =============================================================================

export const API_IMPLEMENTATION = `
"""
Transaction Builder API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import base64

router = APIRouter(prefix="/api/transaction", tags=["Transaction Builder"])


class InstructionData(BaseModel):
    id: str
    type: str
    params: Dict[str, Any]


class TransactionRequest(BaseModel):
    instructions: List[InstructionData]


class BalanceChange(BaseModel):
    account: str
    token: str
    before: int
    after: int
    change: int


class SimulationResult(BaseModel):
    success: bool
    logs: List[str]
    unitsConsumed: int
    error: Optional[str] = None
    balanceChanges: List[BalanceChange]


@router.post("/preview")
async def preview_transaction(request: TransactionRequest):
    """Build transaction preview with fee estimation"""
    try:
        # Build transaction from instructions
        tx_data = await build_transaction(request.instructions)

        return {
            "instructions": [ix.dict() for ix in request.instructions],
            "estimatedFee": tx_data["estimated_fee"],
            "computeUnits": tx_data["compute_units"],
            "signers": tx_data["signers"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/simulate")
async def simulate_transaction(request: TransactionRequest) -> SimulationResult:
    """Simulate transaction without sending"""
    try:
        # Build transaction
        tx_data = await build_transaction(request.instructions)

        # Simulate on Solana
        result = await simulate_on_chain(tx_data["transaction"])

        return SimulationResult(
            success=result["success"],
            logs=result["logs"],
            unitsConsumed=result["units_consumed"],
            error=result.get("error"),
            balanceChanges=result.get("balance_changes", [])
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/send")
async def send_transaction(request: TransactionRequest):
    """Send transaction to network"""
    try:
        # Build transaction
        tx_data = await build_transaction(request.instructions)

        # Send to Solana
        signature = await send_to_network(tx_data["transaction"])

        return {
            "signature": signature,
            "status": "confirmed"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def build_transaction(instructions: List[InstructionData]) -> Dict[str, Any]:
    """Build Solana transaction from instructions"""
    # Implementation would use solana-py or similar
    return {
        "transaction": b"",
        "estimated_fee": 5000,
        "compute_units": 200000,
        "signers": ["wallet_pubkey"]
    }


async def simulate_on_chain(transaction: bytes) -> Dict[str, Any]:
    """Simulate transaction on Solana"""
    # Implementation would use RPC simulateTransaction
    return {
        "success": True,
        "logs": ["Program log: Instruction executed"],
        "units_consumed": 150000,
        "balance_changes": []
    }


async def send_to_network(transaction: bytes) -> str:
    """Send transaction to Solana network"""
    # Implementation would use RPC sendTransaction
    return "mock_signature_abc123"
`;
