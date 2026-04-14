//! MIXI-CUT WAV Decoder CLI
//!
//! Usage: mixi-decode <file.wav>

use std::env;
use std::fs::File;
use std::io::BufReader;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: mixi-decode <file.wav>");
        std::process::exit(1);
    }

    let path = &args[1];
    println!("MIXI-CUT Rust Decoder");
    println!("Decoding: {path}");

    // Simple WAV parser (16-bit PCM stereo only)
    let file = File::open(path).expect("Cannot open file");
    let reader = BufReader::new(file);
    let wav = hound::WavReader::new(reader).expect("Invalid WAV");

    let spec = wav.spec();
    println!("  Format: {} Hz, {}-bit, {} ch",
             spec.sample_rate, spec.bits_per_sample, spec.channels);

    if spec.channels != 2 {
        eprintln!("Error: expected stereo WAV");
        std::process::exit(1);
    }

    let sr = spec.sample_rate as f32;
    let samples: Vec<f32> = wav.into_samples::<i16>()
        .map(|s| s.unwrap() as f32 / 32768.0)
        .collect();

    let n_frames = samples.len() / 2;
    let mut left = Vec::with_capacity(n_frames);
    let mut right = Vec::with_capacity(n_frames);
    for i in 0..n_frames {
        left.push(samples[i * 2]);
        right.push(samples[i * 2 + 1]);
    }

    println!("  Duration: {:.1}s\n", n_frames as f32 / sr);

    let mut dec = mixi_decoder::Decoder::new(mixi_decoder::DecoderConfig {
        sample_rate: sr,
        ..Default::default()
    });

    let block = 128;
    let mut block_count = 0;
    for i in (0..n_frames).step_by(block) {
        let end = (i + block).min(n_frames);
        let r = dec.process(&left[i..end], &right[i..end]);
        let t = (i + block / 2) as f32 / sr;

        // Print every ~1 second
        if i % (sr as usize) < block {
            let lock_bar: String = (0..20)
                .map(|j| if (j as f32) < r.lock * 20.0 { '█' } else { '░' })
                .collect();
            println!("  t={t:6.1}s  speed={:+.3}x  lock=[{lock_bar}] {:.3}  pos={:.2}s",
                     r.speed, r.lock, r.position);
        }
        block_count += 1;
    }

    println!("\n  Decoded {block_count} blocks.");
}
