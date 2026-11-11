class Mosaik < Formula
  desc "Sign in to Mosaik and use its products from a terminal or agent"
  homepage "https://auth.mosaikhq.app"
  url "https://github.com/Sakeliga/mosaic-homebrew/releases/download/rehearsal-v2.0.0-43103350378-1/mosaik-2.0.0.tar.gz"
  sha256 "000036b83c6d630e3d567727159d314e3437a50ab37edb7faf5accf8dde299b2"
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
