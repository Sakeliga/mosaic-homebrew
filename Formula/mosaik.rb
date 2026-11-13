class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  version "2.1.0"
  license :cannot_represent

  on_macos do
    on_arm do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.1.0/mosaik-2.1.0-darwin-arm64.tar.gz"
      sha256 "cb7b40d6d6196511af44f80923d4d7a60923215ea6c9927e8494def4a47aaa77"
    end
    on_intel do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.1.0/mosaik-2.1.0-darwin-x64.tar.gz"
      sha256 "72c9b892e394c973539794f44815fce6efdd324c83f8aec35ed3718eb35e2ac6"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.1.0/mosaik-2.1.0-linux-arm64.tar.gz"
      sha256 "4307b9e963543c4f7460de974dce1c5bc6277ed721a4cdc3e8a602eba17ddb65"
    end
    on_intel do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.1.0/mosaik-2.1.0-linux-x64.tar.gz"
      sha256 "ea844ff09e181e20649ddcd81b06f41a42fc207bcb827a0edf7c76afc53d6ef6"
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
