class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  # The first release pull request replaces this placeholder version, URL and hash.
  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v0.0.0/mosaik-0.0.0.tar.gz"
  version "0.0.0"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license :cannot_represent

  depends_on "node@24"

  def install
    libexec.install "mosaik.mjs"
    (share/"mosaik").install "guide.md"
    prefix.install "LICENSE"
    (bin/"mosaik").write <<~SH
      #!/bin/sh
      exec "#{formula_opt_bin("node@24")}/node" "#{libexec}/mosaik.mjs" "$@"
    SH
  end

  test do
    assert_equal version.to_s, shell_output("#{bin}/mosaik --version").strip
  end
end
