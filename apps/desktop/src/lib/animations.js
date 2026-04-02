/**
 * Animation Utilities
 * CSS-based animations for smooth transitions without Framer Motion dependency
 * Can be easily replaced with Framer Motion if desired
 */

/**
 * Fade In animation variants
 */
export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
}

/**
 * Slide Up animation
 */
export const slideUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
  transition: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
}

/**
 * Slide In from Right
 */
export const slideInRight = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 20 },
  transition: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
}

/**
 * Scale In animation
 */
export const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.2, ease: [0.4, 0, 0.2, 1] },
}

/**
 * Stagger children animations
 */
export const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1,
    },
  },
}

/**
 * Spring animation config
 */
export const spring = {
  type: 'spring',
  stiffness: 400,
  damping: 30,
}

/**
 * CSS class-based animations
 * Apply these classes for CSS-only animations
 */
export const cssAnimations = {
  fadeIn: 'animate-fade-in',
  slideUp: 'animate-slide-up',
  slideIn: 'animate-slide-in',
  scaleIn: 'animate-scale-in',
  bounce: 'animate-bounce',
  pulse: 'animate-pulse',
  spin: 'animate-spin',
}

/**
 * Transition timing functions
 */
export const easings = {
  default: 'cubic-bezier(0.4, 0, 0.2, 1)',
  in: 'cubic-bezier(0.4, 0, 1, 1)',
  out: 'cubic-bezier(0, 0, 0.2, 1)',
  inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
  spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
}

/**
 * Duration presets (in ms)
 */
export const durations = {
  fast: 150,
  normal: 200,
  slow: 300,
  slower: 500,
}

/**
 * Apply staggered animation to children
 * @param {number} index - Child index
 * @param {number} delay - Base delay in ms
 * @returns {object} Style object with animation delay
 */
export function staggerDelay(index, delay = 50) {
  return {
    animationDelay: `${index * delay}ms`,
  }
}

/**
 * Create a transition style object
 * @param {string} property - CSS property to animate
 * @param {string} duration - Duration key from durations
 * @param {string} easing - Easing key from easings
 * @returns {object} Style object
 */
export function createTransition(property = 'all', duration = 'normal', easing = 'default') {
  return {
    transition: `${property} ${durations[duration]}ms ${easings[easing]}`,
  }
}

export default {
  fadeIn,
  slideUp,
  slideInRight,
  scaleIn,
  staggerContainer,
  spring,
  cssAnimations,
  easings,
  durations,
  staggerDelay,
  createTransition,
}
