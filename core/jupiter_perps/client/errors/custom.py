import typing
from anchorpy.error import ProgramError


class MathOverflow(ProgramError):
    def __init__(self) -> None:
        super().__init__(6000, "Overflow in arithmetic operation")

    code = 6000
    name = "MathOverflow"
    msg = "Overflow in arithmetic operation"


class UnsupportedOracle(ProgramError):
    def __init__(self) -> None:
        super().__init__(6001, "Unsupported price oracle")

    code = 6001
    name = "UnsupportedOracle"
    msg = "Unsupported price oracle"


class InvalidOracleAccount(ProgramError):
    def __init__(self) -> None:
        super().__init__(6002, "Invalid oracle account")

    code = 6002
    name = "InvalidOracleAccount"
    msg = "Invalid oracle account"


class StaleOraclePrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6003, "Stale oracle price")

    code = 6003
    name = "StaleOraclePrice"
    msg = "Stale oracle price"


class InvalidOraclePrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6004, "Invalid oracle price")

    code = 6004
    name = "InvalidOraclePrice"
    msg = "Invalid oracle price"


class InvalidEnvironment(ProgramError):
    def __init__(self) -> None:
        super().__init__(6005, "Instruction is not allowed in production")

    code = 6005
    name = "InvalidEnvironment"
    msg = "Instruction is not allowed in production"


class InvalidCollateralAccount(ProgramError):
    def __init__(self) -> None:
        super().__init__(6006, "Invalid collateral account")

    code = 6006
    name = "InvalidCollateralAccount"
    msg = "Invalid collateral account"


class InvalidCollateralAmount(ProgramError):
    def __init__(self) -> None:
        super().__init__(6007, "Invalid collateral amount")

    code = 6007
    name = "InvalidCollateralAmount"
    msg = "Invalid collateral amount"


class CollateralSlippage(ProgramError):
    def __init__(self) -> None:
        super().__init__(6008, "Collateral slippage")

    code = 6008
    name = "CollateralSlippage"
    msg = "Collateral slippage"


class InvalidPositionState(ProgramError):
    def __init__(self) -> None:
        super().__init__(6009, "Invalid position state")

    code = 6009
    name = "InvalidPositionState"
    msg = "Invalid position state"


class InvalidPerpetualsConfig(ProgramError):
    def __init__(self) -> None:
        super().__init__(6010, "Invalid perpetuals config")

    code = 6010
    name = "InvalidPerpetualsConfig"
    msg = "Invalid perpetuals config"


class InvalidPoolConfig(ProgramError):
    def __init__(self) -> None:
        super().__init__(6011, "Invalid pool config")

    code = 6011
    name = "InvalidPoolConfig"
    msg = "Invalid pool config"


class InvalidInstruction(ProgramError):
    def __init__(self) -> None:
        super().__init__(6012, "Invalid instruction")

    code = 6012
    name = "InvalidInstruction"
    msg = "Invalid instruction"


class InvalidCustodyConfig(ProgramError):
    def __init__(self) -> None:
        super().__init__(6013, "Invalid custody config")

    code = 6013
    name = "InvalidCustodyConfig"
    msg = "Invalid custody config"


class InvalidCustodyBalance(ProgramError):
    def __init__(self) -> None:
        super().__init__(6014, "Invalid custody balance")

    code = 6014
    name = "InvalidCustodyBalance"
    msg = "Invalid custody balance"


class InvalidArgument(ProgramError):
    def __init__(self) -> None:
        super().__init__(6015, "Invalid argument")

    code = 6015
    name = "InvalidArgument"
    msg = "Invalid argument"


class InvalidPositionRequest(ProgramError):
    def __init__(self) -> None:
        super().__init__(6016, "Invalid position request")

    code = 6016
    name = "InvalidPositionRequest"
    msg = "Invalid position request"


class InvalidPositionRequestInputAta(ProgramError):
    def __init__(self) -> None:
        super().__init__(6017, "Invalid position request input ata")

    code = 6017
    name = "InvalidPositionRequestInputAta"
    msg = "Invalid position request input ata"


class InvalidMint(ProgramError):
    def __init__(self) -> None:
        super().__init__(6018, "Invalid mint")

    code = 6018
    name = "InvalidMint"
    msg = "Invalid mint"


class InsufficientTokenAmount(ProgramError):
    def __init__(self) -> None:
        super().__init__(6019, "Insufficient token amount")

    code = 6019
    name = "InsufficientTokenAmount"
    msg = "Insufficient token amount"


class InsufficientAmountReturned(ProgramError):
    def __init__(self) -> None:
        super().__init__(6020, "Insufficient token amount returned")

    code = 6020
    name = "InsufficientAmountReturned"
    msg = "Insufficient token amount returned"


class MaxPriceSlippage(ProgramError):
    def __init__(self) -> None:
        super().__init__(6021, "Price slippage limit exceeded")

    code = 6021
    name = "MaxPriceSlippage"
    msg = "Price slippage limit exceeded"


class MaxLeverage(ProgramError):
    def __init__(self) -> None:
        super().__init__(6022, "Position leverage limit exceeded")

    code = 6022
    name = "MaxLeverage"
    msg = "Position leverage limit exceeded"


class CustodyAmountLimit(ProgramError):
    def __init__(self) -> None:
        super().__init__(6023, "Custody amount limit exceeded")

    code = 6023
    name = "CustodyAmountLimit"
    msg = "Custody amount limit exceeded"


class PoolAmountLimit(ProgramError):
    def __init__(self) -> None:
        super().__init__(6024, "Pool amount limit exceeded")

    code = 6024
    name = "PoolAmountLimit"
    msg = "Pool amount limit exceeded"


class PersonalPoolAmountLimit(ProgramError):
    def __init__(self) -> None:
        super().__init__(6025, "Personal pool amount limit exceeded")

    code = 6025
    name = "PersonalPoolAmountLimit"
    msg = "Personal pool amount limit exceeded"


class UnsupportedToken(ProgramError):
    def __init__(self) -> None:
        super().__init__(6026, "Token is not supported")

    code = 6026
    name = "UnsupportedToken"
    msg = "Token is not supported"


class InstructionNotAllowed(ProgramError):
    def __init__(self) -> None:
        super().__init__(6027, "Instruction is not allowed at this time")

    code = 6027
    name = "InstructionNotAllowed"
    msg = "Instruction is not allowed at this time"


class JupiterProgramMismatch(ProgramError):
    def __init__(self) -> None:
        super().__init__(6028, "Jupiter Program ID mismatch")

    code = 6028
    name = "JupiterProgramMismatch"
    msg = "Jupiter Program ID mismatch"


class ProgramMismatch(ProgramError):
    def __init__(self) -> None:
        super().__init__(6029, "Program ID mismatch")

    code = 6029
    name = "ProgramMismatch"
    msg = "Program ID mismatch"


class AddressMismatch(ProgramError):
    def __init__(self) -> None:
        super().__init__(6030, "Address mismatch")

    code = 6030
    name = "AddressMismatch"
    msg = "Address mismatch"


class KeeperATAMissing(ProgramError):
    def __init__(self) -> None:
        super().__init__(6031, "Missing keeper ATA")

    code = 6031
    name = "KeeperATAMissing"
    msg = "Missing keeper ATA"


class SwapAmountMismatch(ProgramError):
    def __init__(self) -> None:
        super().__init__(6032, "Swap amount mismatch")

    code = 6032
    name = "SwapAmountMismatch"
    msg = "Swap amount mismatch"


class CPINotAllowed(ProgramError):
    def __init__(self) -> None:
        super().__init__(6033, "CPI not allowed")

    code = 6033
    name = "CPINotAllowed"
    msg = "CPI not allowed"


class InvalidKeeper(ProgramError):
    def __init__(self) -> None:
        super().__init__(6034, "Invalid Keeper")

    code = 6034
    name = "InvalidKeeper"
    msg = "Invalid Keeper"


class ExceedExecutionPeriod(ProgramError):
    def __init__(self) -> None:
        super().__init__(6035, "Exceed execution period")

    code = 6035
    name = "ExceedExecutionPeriod"
    msg = "Exceed execution period"


class InvalidRequestType(ProgramError):
    def __init__(self) -> None:
        super().__init__(6036, "Invalid Request Type")

    code = 6036
    name = "InvalidRequestType"
    msg = "Invalid Request Type"


class InvalidTriggerPrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6037, "Invalid Trigger Price")

    code = 6037
    name = "InvalidTriggerPrice"
    msg = "Invalid Trigger Price"


class TriggerPriceSlippage(ProgramError):
    def __init__(self) -> None:
        super().__init__(6038, "Trigger Price Slippage")

    code = 6038
    name = "TriggerPriceSlippage"
    msg = "Trigger Price Slippage"


class MissingTriggerPrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6039, "Missing Trigger Price")

    code = 6039
    name = "MissingTriggerPrice"
    msg = "Missing Trigger Price"


class MissingPriceSlippage(ProgramError):
    def __init__(self) -> None:
        super().__init__(6040, "Missing Price Slippage")

    code = 6040
    name = "MissingPriceSlippage"
    msg = "Missing Price Slippage"


class InvalidPriceCalcMode(ProgramError):
    def __init__(self) -> None:
        super().__init__(6041, "Invalid Price Calc Mode")

    code = 6041
    name = "InvalidPriceCalcMode"
    msg = "Invalid Price Calc Mode"


class RequestUpdatedTooRecent(ProgramError):
    def __init__(self) -> None:
        super().__init__(6042, "Request Updated Too Recent")

    code = 6042
    name = "RequestUpdatedTooRecent"
    msg = "Request Updated Too Recent"


class ExceedTokenWeightage(ProgramError):
    def __init__(self) -> None:
        super().__init__(6043, "Exceed Token Weightage")

    code = 6043
    name = "ExceedTokenWeightage"
    msg = "Exceed Token Weightage"


class OraclePublishTimeTooEarly(ProgramError):
    def __init__(self) -> None:
        super().__init__(6044, "Oracle Publish Time Too Early")

    code = 6044
    name = "OraclePublishTimeTooEarly"
    msg = "Oracle Publish Time Too Early"


class PullOraclePublishTimeTooEarly(ProgramError):
    def __init__(self) -> None:
        super().__init__(6045, "Pull Oracle Publish Time Too Early")

    code = 6045
    name = "PullOraclePublishTimeTooEarly"
    msg = "Pull Oracle Publish Time Too Early"


class StalePullOraclePrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6046, "Stale Pull Oracle Price")

    code = 6046
    name = "StalePullOraclePrice"
    msg = "Stale Pull Oracle Price"


class InvalidPullOraclePrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6047, "Invalid Pull Oracle Price")

    code = 6047
    name = "InvalidPullOraclePrice"
    msg = "Invalid Pull Oracle Price"


class PullOracleNotVerified(ProgramError):
    def __init__(self) -> None:
        super().__init__(6048, "Pull Oracle Not Verified")

    code = 6048
    name = "PullOracleNotVerified"
    msg = "Pull Oracle Not Verified"


class PriceDiffTooLarge(ProgramError):
    def __init__(self) -> None:
        super().__init__(6049, "Price Diff Between Pull and Push Oracle is Too Large")

    code = 6049
    name = "PriceDiffTooLarge"
    msg = "Price Diff Between Pull and Push Oracle is Too Large"


class InvalidDovesOraclePrice(ProgramError):
    def __init__(self) -> None:
        super().__init__(6050, "Invalid Doves Oracle Price")

    code = 6050
    name = "InvalidDovesOraclePrice"
    msg = "Invalid Doves Oracle Price"


class InvalidRequestTime(ProgramError):
    def __init__(self) -> None:
        super().__init__(6051, "Invalid Request Time")

    code = 6051
    name = "InvalidRequestTime"
    msg = "Invalid Request Time"


class PositionUpdatedTooRecent(ProgramError):
    def __init__(self) -> None:
        super().__init__(6052, "Position Updated Too Recent")

    code = 6052
    name = "PositionUpdatedTooRecent"
    msg = "Position Updated Too Recent"


class LedgerTokenAccountDoesNotMatch(ProgramError):
    def __init__(self) -> None:
        super().__init__(6053, "Ledger token account does not match")

    code = 6053
    name = "LedgerTokenAccountDoesNotMatch"
    msg = "Ledger token account does not match"


class InvalidTokenLedger(ProgramError):
    def __init__(self) -> None:
        super().__init__(6054, "Invalid token ledger")

    code = 6054
    name = "InvalidTokenLedger"
    msg = "Invalid token ledger"


class OraclePriceDifferenceTooLarge(ProgramError):
    def __init__(self) -> None:
        super().__init__(6055, "Oracle Price Difference Too Large")

    code = 6055
    name = "OraclePriceDifferenceTooLarge"
    msg = "Oracle Price Difference Too Large"


class InvalidOracleSigner(ProgramError):
    def __init__(self) -> None:
        super().__init__(6056, "Invalid Oracle Signer")

    code = 6056
    name = "InvalidOracleSigner"
    msg = "Invalid Oracle Signer"


class InvalidOracleTimestamp(ProgramError):
    def __init__(self) -> None:
        super().__init__(6057, "Invalid Oracle Timestamp")

    code = 6057
    name = "InvalidOracleTimestamp"
    msg = "Invalid Oracle Timestamp"


class InvalidMaxGlobalLongSize(ProgramError):
    def __init__(self) -> None:
        super().__init__(6058, "New Max Global Long Size Too Low")

    code = 6058
    name = "InvalidMaxGlobalLongSize"
    msg = "New Max Global Long Size Too Low"


class InvalidMaxGlobalShortSize(ProgramError):
    def __init__(self) -> None:
        super().__init__(6059, "New Max Global Short Size Too Low")

    code = 6059
    name = "InvalidMaxGlobalShortSize"
    msg = "New Max Global Short Size Too Low"


class BorrowsDisabled(ProgramError):
    def __init__(self) -> None:
        super().__init__(6060, "Borrows disabled for this custody")

    code = 6060
    name = "BorrowsDisabled"
    msg = "Borrows disabled for this custody"


class BorrowLimitsExceeded(ProgramError):
    def __init__(self) -> None:
        super().__init__(6061, "Borrows limit exceeded for this custody")

    code = 6061
    name = "BorrowLimitsExceeded"
    msg = "Borrows limit exceeded for this custody"


class WithdrawExceedsMarginLimits(ProgramError):
    def __init__(self) -> None:
        super().__init__(6062, "Withdraw exceeds margin of the custody")

    code = 6062
    name = "WithdrawExceedsMarginLimits"
    msg = "Withdraw exceeds margin of the custody"


class CannotLiquidate(ProgramError):
    def __init__(self) -> None:
        super().__init__(6063, "Cannot liquidate")

    code = 6063
    name = "CannotLiquidate"
    msg = "Cannot liquidate"


CustomError = typing.Union[
    MathOverflow,
    UnsupportedOracle,
    InvalidOracleAccount,
    StaleOraclePrice,
    InvalidOraclePrice,
    InvalidEnvironment,
    InvalidCollateralAccount,
    InvalidCollateralAmount,
    CollateralSlippage,
    InvalidPositionState,
    InvalidPerpetualsConfig,
    InvalidPoolConfig,
    InvalidInstruction,
    InvalidCustodyConfig,
    InvalidCustodyBalance,
    InvalidArgument,
    InvalidPositionRequest,
    InvalidPositionRequestInputAta,
    InvalidMint,
    InsufficientTokenAmount,
    InsufficientAmountReturned,
    MaxPriceSlippage,
    MaxLeverage,
    CustodyAmountLimit,
    PoolAmountLimit,
    PersonalPoolAmountLimit,
    UnsupportedToken,
    InstructionNotAllowed,
    JupiterProgramMismatch,
    ProgramMismatch,
    AddressMismatch,
    KeeperATAMissing,
    SwapAmountMismatch,
    CPINotAllowed,
    InvalidKeeper,
    ExceedExecutionPeriod,
    InvalidRequestType,
    InvalidTriggerPrice,
    TriggerPriceSlippage,
    MissingTriggerPrice,
    MissingPriceSlippage,
    InvalidPriceCalcMode,
    RequestUpdatedTooRecent,
    ExceedTokenWeightage,
    OraclePublishTimeTooEarly,
    PullOraclePublishTimeTooEarly,
    StalePullOraclePrice,
    InvalidPullOraclePrice,
    PullOracleNotVerified,
    PriceDiffTooLarge,
    InvalidDovesOraclePrice,
    InvalidRequestTime,
    PositionUpdatedTooRecent,
    LedgerTokenAccountDoesNotMatch,
    InvalidTokenLedger,
    OraclePriceDifferenceTooLarge,
    InvalidOracleSigner,
    InvalidOracleTimestamp,
    InvalidMaxGlobalLongSize,
    InvalidMaxGlobalShortSize,
    BorrowsDisabled,
    BorrowLimitsExceeded,
    WithdrawExceedsMarginLimits,
    CannotLiquidate,
]
CUSTOM_ERROR_MAP: dict[int, CustomError] = {
    6000: MathOverflow(),
    6001: UnsupportedOracle(),
    6002: InvalidOracleAccount(),
    6003: StaleOraclePrice(),
    6004: InvalidOraclePrice(),
    6005: InvalidEnvironment(),
    6006: InvalidCollateralAccount(),
    6007: InvalidCollateralAmount(),
    6008: CollateralSlippage(),
    6009: InvalidPositionState(),
    6010: InvalidPerpetualsConfig(),
    6011: InvalidPoolConfig(),
    6012: InvalidInstruction(),
    6013: InvalidCustodyConfig(),
    6014: InvalidCustodyBalance(),
    6015: InvalidArgument(),
    6016: InvalidPositionRequest(),
    6017: InvalidPositionRequestInputAta(),
    6018: InvalidMint(),
    6019: InsufficientTokenAmount(),
    6020: InsufficientAmountReturned(),
    6021: MaxPriceSlippage(),
    6022: MaxLeverage(),
    6023: CustodyAmountLimit(),
    6024: PoolAmountLimit(),
    6025: PersonalPoolAmountLimit(),
    6026: UnsupportedToken(),
    6027: InstructionNotAllowed(),
    6028: JupiterProgramMismatch(),
    6029: ProgramMismatch(),
    6030: AddressMismatch(),
    6031: KeeperATAMissing(),
    6032: SwapAmountMismatch(),
    6033: CPINotAllowed(),
    6034: InvalidKeeper(),
    6035: ExceedExecutionPeriod(),
    6036: InvalidRequestType(),
    6037: InvalidTriggerPrice(),
    6038: TriggerPriceSlippage(),
    6039: MissingTriggerPrice(),
    6040: MissingPriceSlippage(),
    6041: InvalidPriceCalcMode(),
    6042: RequestUpdatedTooRecent(),
    6043: ExceedTokenWeightage(),
    6044: OraclePublishTimeTooEarly(),
    6045: PullOraclePublishTimeTooEarly(),
    6046: StalePullOraclePrice(),
    6047: InvalidPullOraclePrice(),
    6048: PullOracleNotVerified(),
    6049: PriceDiffTooLarge(),
    6050: InvalidDovesOraclePrice(),
    6051: InvalidRequestTime(),
    6052: PositionUpdatedTooRecent(),
    6053: LedgerTokenAccountDoesNotMatch(),
    6054: InvalidTokenLedger(),
    6055: OraclePriceDifferenceTooLarge(),
    6056: InvalidOracleSigner(),
    6057: InvalidOracleTimestamp(),
    6058: InvalidMaxGlobalLongSize(),
    6059: InvalidMaxGlobalShortSize(),
    6060: BorrowsDisabled(),
    6061: BorrowLimitsExceeded(),
    6062: WithdrawExceedsMarginLimits(),
    6063: CannotLiquidate(),
}


def from_code(code: int) -> typing.Optional[CustomError]:
    maybe_err = CUSTOM_ERROR_MAP.get(code)
    if maybe_err is None:
        return None
    return maybe_err
