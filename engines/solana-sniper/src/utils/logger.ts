import winston from 'winston';

const { combine, timestamp, printf, colorize } = winston.format;

const logFormat = printf(({ level, message, timestamp: ts, module: mod, ...meta }) => {
  const moduleTag = mod ? `[${mod}]` : '';
  const metaStr = Object.keys(meta).length > 0 ? ` ${JSON.stringify(meta)}` : '';
  return `${ts} ${level} ${moduleTag} ${message}${metaStr}`;
});

export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  format: combine(
    timestamp({ format: 'HH:mm:ss.SSS' }),
    logFormat
  ),
  transports: [
    new winston.transports.Console({
      format: combine(colorize(), timestamp({ format: 'HH:mm:ss.SSS' }), logFormat),
    }),
    new winston.transports.File({
      filename: 'logs/sniper.log',
      maxsize: 10_000_000, // 10MB
      maxFiles: 5,
    }),
    new winston.transports.File({
      filename: 'logs/errors.log',
      level: 'error',
      maxsize: 10_000_000,
      maxFiles: 3,
    }),
  ],
});

export function createModuleLogger(moduleName: string): winston.Logger {
  return logger.child({ module: moduleName });
}
