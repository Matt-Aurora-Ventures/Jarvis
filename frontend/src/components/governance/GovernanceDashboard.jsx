import React, { useState, useMemo, useCallback } from 'react'
import {
  Vote,
  Users,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  ExternalLink,
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Wallet,
  FileText,
  BarChart3,
  Calendar,
  ThumbsUp,
  ThumbsDown,
  Minus,
  TrendingUp,
  Shield,
  Award,
  Bell,
  BellOff,
  Eye,
  MessageSquare,
  Copy,
  Check,
  X,
  Zap,
  DollarSign
} from 'lucide-react'

// Proposal status
const PROPOSAL_STATUS = {
  ACTIVE: { label: 'Active', color: 'text-green-400', bg: 'bg-green-400/10', icon: Clock },
  PASSED: { label: 'Passed', color: 'text-blue-400', bg: 'bg-blue-400/10', icon: CheckCircle },
  REJECTED: { label: 'Rejected', color: 'text-red-400', bg: 'bg-red-400/10', icon: XCircle },
  PENDING: { label: 'Pending', color: 'text-yellow-400', bg: 'bg-yellow-400/10', icon: AlertCircle },
  EXECUTED: { label: 'Executed', color: 'text-purple-400', bg: 'bg-purple-400/10', icon: Zap },
  CANCELLED: { label: 'Cancelled', color: 'text-slate-400', bg: 'bg-slate-400/10', icon: X }
}

// Vote options
const VOTE_OPTIONS = {
  FOR: { label: 'For', color: 'text-green-400', bg: 'bg-green-400', icon: ThumbsUp },
  AGAINST: { label: 'Against', color: 'text-red-400', bg: 'bg-red-400', icon: ThumbsDown },
  ABSTAIN: { label: 'Abstain', color: 'text-slate-400', bg: 'bg-slate-400', icon: Minus }
}

// Protocol categories
const PROTOCOL_CATEGORIES = {
  DEFI: { label: 'DeFi', color: 'text-blue-400', bg: 'bg-blue-400/10' },
  DEX: { label: 'DEX', color: 'text-purple-400', bg: 'bg-purple-400/10' },
  LENDING: { label: 'Lending', color: 'text-cyan-400', bg: 'bg-cyan-400/10' },
  NFT: { label: 'NFT', color: 'text-pink-400', bg: 'bg-pink-400/10' },
  GAMING: { label: 'Gaming', color: 'text-orange-400', bg: 'bg-orange-400/10' },
  INFRASTRUCTURE: { label: 'Infrastructure', color: 'text-green-400', bg: 'bg-green-400/10' },
  DAO: { label: 'DAO', color: 'text-yellow-400', bg: 'bg-yellow-400/10' }
}

// Mock protocols
const mockProtocols = [
  {
    id: 'jupiter',
    name: 'Jupiter',
    logo: null,
    category: 'DEX',
    tokenSymbol: 'JUP',
    votingPower: 15000,
    delegatedTo: null,
    activeProposals: 2,
    totalProposals: 45,
    participationRate: 78
  },
  {
    id: 'marinade',
    name: 'Marinade Finance',
    logo: null,
    category: 'DEFI',
    tokenSymbol: 'MNDE',
    votingPower: 25000,
    delegatedTo: 'validator.sol',
    activeProposals: 1,
    totalProposals: 32,
    participationRate: 65
  },
  {
    id: 'realms',
    name: 'Realms',
    logo: null,
    category: 'DAO',
    tokenSymbol: 'REALM',
    votingPower: 5000,
    delegatedTo: null,
    activeProposals: 3,
    totalProposals: 89,
    participationRate: 45
  },
  {
    id: 'raydium',
    name: 'Raydium',
    logo: null,
    category: 'DEX',
    tokenSymbol: 'RAY',
    votingPower: 8000,
    delegatedTo: null,
    activeProposals: 0,
    totalProposals: 28,
    participationRate: 52
  }
]

// Mock proposals
const mockProposals = [
  {
    id: 'p1',
    protocol: 'jupiter',
    protocolName: 'Jupiter',
    title: 'JUP-42: Increase Protocol Fee to 0.1%',
    description: 'This proposal seeks to increase the protocol fee from 0.05% to 0.1% to fund further development and community initiatives.',
    status: 'ACTIVE',
    category: 'TREASURY',
    author: 'meow.sol',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 2,
    endTime: Date.now() + 1000 * 60 * 60 * 24 * 3,
    quorum: 10000000,
    currentVotes: 8500000,
    votes: {
      for: 6800000,
      against: 1200000,
      abstain: 500000
    },
    yourVote: null,
    yourVotingPower: 15000,
    discussionUrl: 'https://forum.jup.ag/proposal-42',
    ipfsHash: 'QmXyz...'
  },
  {
    id: 'p2',
    protocol: 'jupiter',
    protocolName: 'Jupiter',
    title: 'JUP-43: Add New Trading Pair BONK/SOL',
    description: 'Proposal to add concentrated liquidity pool for BONK/SOL pair with optimized fee tiers.',
    status: 'ACTIVE',
    category: 'PROTOCOL',
    author: 'whale.sol',
    createdAt: Date.now() - 1000 * 60 * 60 * 24,
    endTime: Date.now() + 1000 * 60 * 60 * 24 * 5,
    quorum: 10000000,
    currentVotes: 4200000,
    votes: {
      for: 3800000,
      against: 200000,
      abstain: 200000
    },
    yourVote: 'FOR',
    yourVotingPower: 15000,
    discussionUrl: 'https://forum.jup.ag/proposal-43',
    ipfsHash: 'QmAbc...'
  },
  {
    id: 'p3',
    protocol: 'marinade',
    protocolName: 'Marinade Finance',
    title: 'MNDE-18: Validator Delegation Strategy Update',
    description: 'Update the validator delegation algorithm to prioritize decentralization metrics over pure APY.',
    status: 'PASSED',
    category: 'PROTOCOL',
    author: 'decentralize.sol',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 7,
    endTime: Date.now() - 1000 * 60 * 60 * 24,
    quorum: 5000000,
    currentVotes: 7500000,
    votes: {
      for: 6200000,
      against: 800000,
      abstain: 500000
    },
    yourVote: 'FOR',
    yourVotingPower: 25000,
    discussionUrl: 'https://forum.marinade.finance/proposal-18',
    ipfsHash: 'QmDef...'
  },
  {
    id: 'p4',
    protocol: 'realms',
    protocolName: 'Realms',
    title: 'REALM-67: Community Treasury Allocation',
    description: 'Allocate 500,000 REALM tokens from treasury to fund ecosystem grants program for Q2 2024.',
    status: 'ACTIVE',
    category: 'TREASURY',
    author: 'community.sol',
    createdAt: Date.now() - 1000 * 60 * 60 * 48,
    endTime: Date.now() + 1000 * 60 * 60 * 24 * 2,
    quorum: 2000000,
    currentVotes: 1800000,
    votes: {
      for: 1500000,
      against: 200000,
      abstain: 100000
    },
    yourVote: null,
    yourVotingPower: 5000,
    discussionUrl: 'https://forum.realms.today/proposal-67',
    ipfsHash: 'QmGhi...'
  },
  {
    id: 'p5',
    protocol: 'realms',
    protocolName: 'Realms',
    title: 'REALM-68: Governance Parameter Changes',
    description: 'Reduce voting period from 7 days to 5 days and increase quorum from 10% to 15%.',
    status: 'PENDING',
    category: 'GOVERNANCE',
    author: 'gov.sol',
    createdAt: Date.now() - 1000 * 60 * 60 * 12,
    endTime: Date.now() + 1000 * 60 * 60 * 24 * 7,
    quorum: 2000000,
    currentVotes: 0,
    votes: {
      for: 0,
      against: 0,
      abstain: 0
    },
    yourVote: null,
    yourVotingPower: 5000,
    discussionUrl: 'https://forum.realms.today/proposal-68',
    ipfsHash: 'QmJkl...'
  },
  {
    id: 'p6',
    protocol: 'raydium',
    protocolName: 'Raydium',
    title: 'RAY-21: Fee Redistribution Model',
    description: 'Implement new fee redistribution model directing 30% of fees to RAY stakers.',
    status: 'REJECTED',
    category: 'TREASURY',
    author: 'staker.sol',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 14,
    endTime: Date.now() - 1000 * 60 * 60 * 24 * 7,
    quorum: 8000000,
    currentVotes: 9200000,
    votes: {
      for: 3500000,
      against: 5200000,
      abstain: 500000
    },
    yourVote: 'AGAINST',
    yourVotingPower: 8000,
    discussionUrl: 'https://forum.raydium.io/proposal-21',
    ipfsHash: 'QmMno...'
  }
]

// Format helpers
const formatNumber = (num) => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toLocaleString()
}

const formatTime = (timestamp) => {
  const diff = timestamp - Date.now()
  const absDiff = Math.abs(diff)

  if (diff > 0) {
    if (absDiff < 3600000) return `${Math.floor(absDiff / 60000)}m left`
    if (absDiff < 86400000) return `${Math.floor(absDiff / 3600000)}h left`
    return `${Math.floor(absDiff / 86400000)}d left`
  } else {
    if (absDiff < 3600000) return `${Math.floor(absDiff / 60000)}m ago`
    if (absDiff < 86400000) return `${Math.floor(absDiff / 3600000)}h ago`
    return `${Math.floor(absDiff / 86400000)}d ago`
  }
}

const formatDate = (timestamp) => {
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

// Protocol card
const ProtocolCard = ({ protocol, onSelect, isSelected }) => {
  const category = PROTOCOL_CATEGORIES[protocol.category]

  return (
    <div
      onClick={() => onSelect(protocol.id)}
      className={`p-4 rounded-xl border cursor-pointer transition-all ${
        isSelected
          ? 'bg-blue-500/10 border-blue-500'
          : 'bg-white/5 border-white/10 hover:border-white/20'
      }`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center font-bold text-white">
          {protocol.name.slice(0, 2)}
        </div>
        <div>
          <div className="font-medium text-white">{protocol.name}</div>
          <span className={`text-xs px-2 py-0.5 rounded ${category.bg} ${category.color}`}>
            {category.label}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-slate-500">Voting Power</div>
          <div className="text-sm font-medium text-white">
            {formatNumber(protocol.votingPower)} {protocol.tokenSymbol}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Active</div>
          <div className="text-sm font-medium text-green-400">
            {protocol.activeProposals} proposals
          </div>
        </div>
      </div>

      {protocol.delegatedTo && (
        <div className="mt-3 pt-3 border-t border-white/10">
          <div className="text-xs text-slate-500">Delegated to</div>
          <div className="text-sm text-blue-400 truncate">{protocol.delegatedTo}</div>
        </div>
      )}
    </div>
  )
}

// Status badge
const StatusBadge = ({ status }) => {
  const statusInfo = PROPOSAL_STATUS[status]
  const IconComponent = statusInfo.icon

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${statusInfo.bg} ${statusInfo.color}`}>
      <IconComponent size={12} />
      {statusInfo.label}
    </span>
  )
}

// Vote bar
const VoteBar = ({ votes, quorum }) => {
  const total = votes.for + votes.against + votes.abstain
  const forPercent = total > 0 ? (votes.for / total) * 100 : 0
  const againstPercent = total > 0 ? (votes.against / total) * 100 : 0
  const abstainPercent = total > 0 ? (votes.abstain / total) * 100 : 0
  const quorumPercent = (total / quorum) * 100

  return (
    <div className="space-y-2">
      {/* Vote distribution bar */}
      <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden flex">
        <div style={{ width: `${forPercent}%` }} className="bg-green-500 transition-all" />
        <div style={{ width: `${againstPercent}%` }} className="bg-red-500 transition-all" />
        <div style={{ width: `${abstainPercent}%` }} className="bg-slate-500 transition-all" />
      </div>

      {/* Vote counts */}
      <div className="flex justify-between text-xs">
        <span className="text-green-400">For: {formatNumber(votes.for)} ({forPercent.toFixed(1)}%)</span>
        <span className="text-red-400">Against: {formatNumber(votes.against)} ({againstPercent.toFixed(1)}%)</span>
        <span className="text-slate-400">Abstain: {formatNumber(votes.abstain)}</span>
      </div>

      {/* Quorum progress */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div
            style={{ width: `${Math.min(quorumPercent, 100)}%` }}
            className={`h-full rounded-full transition-all ${quorumPercent >= 100 ? 'bg-green-500' : 'bg-yellow-500'}`}
          />
        </div>
        <span className={`text-xs ${quorumPercent >= 100 ? 'text-green-400' : 'text-yellow-400'}`}>
          {quorumPercent.toFixed(0)}% quorum
        </span>
      </div>
    </div>
  )
}

// Proposal card
const ProposalCard = ({ proposal, onVote, onExpand, isExpanded }) => {
  const status = PROPOSAL_STATUS[proposal.status]
  const canVote = proposal.status === 'ACTIVE' && !proposal.yourVote

  return (
    <div className={`bg-white/5 rounded-xl border transition-all ${
      isExpanded ? 'border-blue-500' : 'border-white/10'
    }`}>
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-4 mb-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm text-slate-500">{proposal.protocolName}</span>
              <StatusBadge status={proposal.status} />
            </div>
            <h3 className="font-medium text-white">{proposal.title}</h3>
          </div>

          {proposal.yourVote && (
            <div className={`px-3 py-1 rounded-lg ${VOTE_OPTIONS[proposal.yourVote].bg}/20`}>
              <span className={`text-xs font-medium ${VOTE_OPTIONS[proposal.yourVote].color}`}>
                Voted {VOTE_OPTIONS[proposal.yourVote].label}
              </span>
            </div>
          )}
        </div>

        {/* Time info */}
        <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
          <span className="flex items-center gap-1">
            <Clock size={12} />
            {formatTime(proposal.endTime)}
          </span>
          <span className="flex items-center gap-1">
            <Users size={12} />
            {formatNumber(proposal.currentVotes)} votes
          </span>
          <span className="flex items-center gap-1">
            <Wallet size={12} />
            {formatNumber(proposal.yourVotingPower)} power
          </span>
        </div>

        {/* Vote bar */}
        <VoteBar votes={proposal.votes} quorum={proposal.quorum} />
      </div>

      {/* Expand toggle */}
      <button
        onClick={() => onExpand(proposal.id)}
        className="w-full px-4 py-2 border-t border-white/5 flex items-center justify-center gap-2 text-sm text-slate-400 hover:bg-white/5 transition-colors"
      >
        {isExpanded ? (
          <>
            <span>Show less</span>
            <ChevronUp size={16} />
          </>
        ) : (
          <>
            <span>Show more</span>
            <ChevronDown size={16} />
          </>
        )}
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="p-4 pt-0 space-y-4">
          <div>
            <div className="text-xs text-slate-500 mb-1">Description</div>
            <p className="text-sm text-slate-300">{proposal.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-slate-500 mb-1">Author</div>
              <div className="text-sm text-blue-400">{proposal.author}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Created</div>
              <div className="text-sm text-slate-300">{formatDate(proposal.createdAt)}</div>
            </div>
          </div>

          <div className="flex gap-2">
            <a
              href={proposal.discussionUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 px-3 bg-white/5 rounded-lg text-sm text-slate-300 hover:bg-white/10 flex items-center justify-center gap-2"
            >
              <MessageSquare size={14} />
              Discussion
            </a>
            <a
              href={`https://ipfs.io/ipfs/${proposal.ipfsHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 px-3 bg-white/5 rounded-lg text-sm text-slate-300 hover:bg-white/10 flex items-center justify-center gap-2"
            >
              <FileText size={14} />
              IPFS
            </a>
          </div>

          {/* Voting buttons */}
          {canVote && (
            <div className="pt-4 border-t border-white/5">
              <div className="text-sm text-slate-400 mb-3">Cast your vote ({formatNumber(proposal.yourVotingPower)} voting power)</div>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => onVote(proposal.id, 'FOR')}
                  className="py-2 px-4 bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded-lg flex items-center justify-center gap-2 transition-colors"
                >
                  <ThumbsUp size={16} />
                  For
                </button>
                <button
                  onClick={() => onVote(proposal.id, 'AGAINST')}
                  className="py-2 px-4 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg flex items-center justify-center gap-2 transition-colors"
                >
                  <ThumbsDown size={16} />
                  Against
                </button>
                <button
                  onClick={() => onVote(proposal.id, 'ABSTAIN')}
                  className="py-2 px-4 bg-slate-500/20 hover:bg-slate-500/30 text-slate-400 rounded-lg flex items-center justify-center gap-2 transition-colors"
                >
                  <Minus size={16} />
                  Abstain
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Voting power summary
const VotingPowerSummary = ({ protocols }) => {
  const totalPower = protocols.reduce((sum, p) => sum + p.votingPower, 0)
  const delegatedPower = protocols.filter(p => p.delegatedTo).reduce((sum, p) => sum + p.votingPower, 0)
  const activePower = totalPower - delegatedPower

  return (
    <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 rounded-xl p-4 border border-purple-500/20">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Award size={18} className="text-purple-400" />
        Your Voting Power
      </h3>

      <div className="grid grid-cols-3 gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{formatNumber(totalPower)}</div>
          <div className="text-xs text-slate-500">Total</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-400">{formatNumber(activePower)}</div>
          <div className="text-xs text-slate-500">Active</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-400">{formatNumber(delegatedPower)}</div>
          <div className="text-xs text-slate-500">Delegated</div>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-white/10 flex items-center justify-between">
        <span className="text-sm text-slate-400">Protocols</span>
        <span className="text-sm font-medium text-white">{protocols.length}</span>
      </div>
    </div>
  )
}

// Activity feed
const ActivityFeed = ({ proposals }) => {
  const recentActivity = proposals
    .filter(p => p.yourVote)
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 5)

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div className="p-4 border-b border-white/10">
        <h3 className="font-medium text-white flex items-center gap-2">
          <Clock size={18} className="text-cyan-400" />
          Recent Activity
        </h3>
      </div>

      {recentActivity.length === 0 ? (
        <div className="p-8 text-center text-slate-500">
          No recent voting activity
        </div>
      ) : (
        <div className="divide-y divide-white/5">
          {recentActivity.map(proposal => (
            <div key={proposal.id} className="p-3 hover:bg-white/5">
              <div className="flex items-center gap-3">
                <div className={`p-1.5 rounded ${VOTE_OPTIONS[proposal.yourVote].bg}/20`}>
                  {React.createElement(VOTE_OPTIONS[proposal.yourVote].icon, {
                    size: 14,
                    className: VOTE_OPTIONS[proposal.yourVote].color
                  })}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-white truncate">{proposal.title}</div>
                  <div className="text-xs text-slate-500">
                    {proposal.protocolName} • {formatDate(proposal.createdAt)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Stats overview
const StatsOverview = ({ protocols, proposals }) => {
  const activeProposals = proposals.filter(p => p.status === 'ACTIVE').length
  const votedProposals = proposals.filter(p => p.yourVote).length
  const avgParticipation = protocols.reduce((sum, p) => sum + p.participationRate, 0) / protocols.length

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Vote size={16} />
          <span className="text-xs">Active Proposals</span>
        </div>
        <div className="text-2xl font-bold text-green-400">{activeProposals}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <CheckCircle size={16} />
          <span className="text-xs">Votes Cast</span>
        </div>
        <div className="text-2xl font-bold text-blue-400">{votedProposals}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Users size={16} />
          <span className="text-xs">Protocols</span>
        </div>
        <div className="text-2xl font-bold text-purple-400">{protocols.length}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <BarChart3 size={16} />
          <span className="text-xs">Avg Participation</span>
        </div>
        <div className="text-2xl font-bold text-yellow-400">{avgParticipation.toFixed(0)}%</div>
      </div>
    </div>
  )
}

// Main GovernanceDashboard component
export const GovernanceDashboard = () => {
  const [protocols] = useState(mockProtocols)
  const [proposals, setProposals] = useState(mockProposals)
  const [selectedProtocol, setSelectedProtocol] = useState(null)
  const [expandedProposal, setExpandedProposal] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [sortBy, setSortBy] = useState('endTime')

  // Filter and sort proposals
  const filteredProposals = useMemo(() => {
    let result = [...proposals]

    // Protocol filter
    if (selectedProtocol) {
      result = result.filter(p => p.protocol === selectedProtocol)
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(p =>
        p.title.toLowerCase().includes(query) ||
        p.description.toLowerCase().includes(query) ||
        p.protocolName.toLowerCase().includes(query)
      )
    }

    // Status filter
    if (statusFilter !== 'ALL') {
      result = result.filter(p => p.status === statusFilter)
    }

    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'endTime':
          return a.endTime - b.endTime
        case 'votes':
          return b.currentVotes - a.currentVotes
        case 'recent':
          return b.createdAt - a.createdAt
        default:
          return a.endTime - b.endTime
      }
    })

    return result
  }, [proposals, selectedProtocol, searchQuery, statusFilter, sortBy])

  const handleVote = useCallback((proposalId, vote) => {
    setProposals(prev => prev.map(p =>
      p.id === proposalId
        ? {
            ...p,
            yourVote: vote,
            currentVotes: p.currentVotes + p.yourVotingPower,
            votes: {
              ...p.votes,
              [vote.toLowerCase()]: p.votes[vote.toLowerCase()] + p.yourVotingPower
            }
          }
        : p
    ))
  }, [])

  const handleExpand = useCallback((proposalId) => {
    setExpandedProposal(expandedProposal === proposalId ? null : proposalId)
  }, [expandedProposal])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Vote className="text-purple-400" />
              Governance Dashboard
            </h1>
            <p className="text-slate-400">Participate in protocol governance and track proposals</p>
          </div>

          <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
            <RefreshCw size={18} />
          </button>
        </div>

        {/* Stats */}
        <StatsOverview protocols={protocols} proposals={proposals} />

        {/* Main grid */}
        <div className="grid lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="space-y-6">
            {/* Voting power */}
            <VotingPowerSummary protocols={protocols} />

            {/* Protocol list */}
            <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10 flex items-center justify-between">
                <h3 className="font-medium text-white">Protocols</h3>
                <button
                  onClick={() => setSelectedProtocol(null)}
                  className={`text-xs ${selectedProtocol ? 'text-blue-400 hover:text-blue-300' : 'text-slate-500'}`}
                >
                  Show all
                </button>
              </div>
              <div className="p-4 space-y-3">
                {protocols.map(protocol => (
                  <ProtocolCard
                    key={protocol.id}
                    protocol={protocol}
                    onSelect={setSelectedProtocol}
                    isSelected={selectedProtocol === protocol.id}
                  />
                ))}
              </div>
            </div>

            {/* Activity feed */}
            <ActivityFeed proposals={proposals} />
          </div>

          {/* Main content */}
          <div className="lg:col-span-3 space-y-6">
            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4">
              {/* Search */}
              <div className="flex-1 relative">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search proposals..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Status filter */}
              <div className="flex gap-2">
                <button
                  onClick={() => setStatusFilter('ALL')}
                  className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                    statusFilter === 'ALL'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  All
                </button>
                {Object.entries(PROPOSAL_STATUS).slice(0, 3).map(([key, value]) => (
                  <button
                    key={key}
                    onClick={() => setStatusFilter(key)}
                    className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                      statusFilter === key
                        ? `${value.bg} ${value.color} border border-current`
                        : 'bg-white/5 text-slate-400 hover:bg-white/10'
                    }`}
                  >
                    {value.label}
                  </button>
                ))}
              </div>

              {/* Sort */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white appearance-none cursor-pointer"
              >
                <option value="endTime">Ending Soon</option>
                <option value="votes">Most Votes</option>
                <option value="recent">Most Recent</option>
              </select>
            </div>

            {/* Proposals list */}
            <div className="space-y-4">
              {filteredProposals.length === 0 ? (
                <div className="bg-white/5 rounded-xl p-12 text-center border border-white/10">
                  <Vote size={48} className="mx-auto mb-4 text-slate-600" />
                  <div className="text-lg text-slate-400 mb-2">No proposals found</div>
                  <div className="text-sm text-slate-500">
                    {searchQuery || statusFilter !== 'ALL'
                      ? 'Try adjusting your search or filters'
                      : 'Check back later for new proposals'
                    }
                  </div>
                </div>
              ) : (
                filteredProposals.map(proposal => (
                  <ProposalCard
                    key={proposal.id}
                    proposal={proposal}
                    onVote={handleVote}
                    onExpand={handleExpand}
                    isExpanded={expandedProposal === proposal.id}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default GovernanceDashboard
