class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  version "2.1.0"
  license :cannot_represent

  on_macos do
    on_arm do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/rehearsal-v2.1.0-43404719668-1/mosaik-2.1.0-darwin-arm64.tar.gz"
      sha256 "c038b37aa9f7f5f33c22f0eeffdc89d17cc8bf3906c01faadba74eeb962a4877"
    end
    on_intel do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/rehearsal-v2.1.0-43404719668-1/mosaik-2.1.0-darwin-x64.tar.gz"
      sha256 "429e935fb74943fb251bce8d9a2d8660c0135cf3d9fa4e073867644f1b8e9db8"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/rehearsal-v2.1.0-43404719668-1/mosaik-2.1.0-linux-arm64.tar.gz"
      sha256 "5738c76da49066002346bb227e7919491050da05e2ed60efb381e06ff2ba2a51"
    end
    on_intel do
      url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/rehearsal-v2.1.0-43404719668-1/mosaik-2.1.0-linux-x64.tar.gz"
      sha256 "16a9aa82e95c99ec538b8f3759589aa487a2ef0292f46e9b8374d803677f6fc0"
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
