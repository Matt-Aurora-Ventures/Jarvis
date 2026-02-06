// Type declarations for maath/random
declare module 'maath/random/dist/maath-random.esm' {
    export function inSphere(array: Float32Array, options: { radius: number }): Float32Array;
    export function onSphere(array: Float32Array, options: { radius: number }): Float32Array;
    export function inBox(array: Float32Array, options: { sides: number[] }): Float32Array;
    export function inCircle(array: Float32Array, options: { radius: number }): Float32Array;
}
