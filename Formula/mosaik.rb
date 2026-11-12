class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/mosaik-v2.0.0/mosaik-2.0.0.tar.gz"
  sha256 "0450b2db79d12eeb5048c3ed568594dfc5a09b7fdc3532f78d61a56f99bd011b"
  license :cannot_represent

  depends_on "node@24"

  def install
    libexec.install "mosaik.mjs"
    pkgshare.install "guide.md"
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
