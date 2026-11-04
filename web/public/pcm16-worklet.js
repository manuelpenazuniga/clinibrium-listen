// AudioWorklet: mic (any sample rate, usually 48 kHz) → 16 kHz mono PCM16 LE,
// posted to the main thread in fixed frames (default 1600 samples = 100 ms).
// Downsampling is a box-filter decimator that handles fractional ratios
// (e.g. 44.1 kHz → 16 kHz): average the input samples that fall in each output slot.
class Pcm16Downsampler extends AudioWorkletProcessor {
  constructor(options) {
    super()
    const o = (options && options.processorOptions) || {}
    this.ratio = sampleRate / (o.targetRate || 16000)
    this.frameSamples = o.frameSamples || 1600
    this.out = new Int16Array(this.frameSamples)
    this.n = 0
    this.acc = 0
    this.count = 0
    this.t = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || input.length === 0) return true
    const len = input[0].length
    const channels = input.length
    for (let i = 0; i < len; i++) {
      let v = 0
      for (let c = 0; c < channels; c++) v += input[c][i]
      this.acc += v / channels
      this.count += 1
      this.t += 1
      if (this.t >= this.ratio) {
        this.t -= this.ratio
        const s = Math.max(-1, Math.min(1, this.acc / this.count))
        this.out[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff
        this.acc = 0
        this.count = 0
        if (this.n === this.frameSamples) {
          this.port.postMessage(this.out.buffer, [this.out.buffer])
          this.out = new Int16Array(this.frameSamples)
          this.n = 0
        }
      }
    }
    return true
  }
}

registerProcessor("pcm16-downsampler", Pcm16Downsampler)
