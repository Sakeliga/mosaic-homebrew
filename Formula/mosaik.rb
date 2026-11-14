class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  version "2.2.0"
  license :cannot_represent

  on_macos do
    on_arm do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.2.0/mosaik-2.2.0-darwin-arm64.tar.gz"
      sha256 "7bcd12d6a68dd456faf06c503e09b831d5c2330a4bac2dd2c4708470ecb28789"
    end
    on_intel do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.2.0/mosaik-2.2.0-darwin-x64.tar.gz"
      sha256 "d2b12d259c51f2047525cb759a5faa2039d78751e3852967d004249575a2a075"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.2.0/mosaik-2.2.0-linux-arm64.tar.gz"
      sha256 "0530888571f0944220bbbcf6cb7bf4220b996ba17d8ceb12386777d455f627e8"
    end
    on_intel do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.2.0/mosaik-2.2.0-linux-x64.tar.gz"
      sha256 "1fc32ac19d8b51a48bfb9a7b43f474781caf12c55af337c9b2d1bb1c05d43ee8"
    end
  end

  def install
    # Homebrew also runs on 32-bit ARM Linux, where `on_arm` selects the 64-bit binary.
    unless Hardware::CPU.is_64_bit?
      odie "mosaik has no binary for a 32-bit machine. Run mosaik-#{version}.cjs with Node 24 instead."
    end

    bin.install "mosaik"
    pkgshare.install "guide.md"
    prefix.install "LICENSE"
  end

  test do
    assert_equal version.to_s, shell_output("#{bin}/mosaik --version").strip
  end
end
