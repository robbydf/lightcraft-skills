param([string]$In, [string]$Out, [double[]]$Angles = @(-6,-4,-2,0,2,4,6), [string]$Region = "0,1,0,1", [int]$W = 900, [int]$Cols = 1)
# Usage: PSX tiltprev.ps1 -In ID.jpg -Out ID-tilt.jpg [-Angles -6,-4,-2,0,2,4,6] [-Region "x0,x1,y0,y1"] [-W 900] [-Cols 2]
# Use it when measurements cannot settle a tilt (tapered towers, lit buildings at night): show the
# sheet to the user on a card and let them pick, then refine with 1-degree steps around the pick.
# Tilt previews: the frame rotated about its centre by each angle (positive = clockwise, like
# crop.straighten), showing -Region (x0,x1,y0,y1 fractions of the frame), with vertical guide lines.
Add-Type -AssemblyName System.Drawing
$Rg = [double[]]($Region -split ","); $src = [System.Drawing.Image]::FromFile($In)
$sw = $src.Width; $sh = $src.Height
$rx0 = $Rg[0] * $sw; $rw = ($Rg[1] - $Rg[0]) * $sw
$ry0 = $Rg[2] * $sh; $rh = ($Rg[3] - $Rg[2]) * $sh
$scale = $W / $rw
$cw = [int]$W; $ch = [int]($rh * $scale)
$n = $Angles.Count; $rows = [math]::Ceiling($n / $Cols)
$sheet = New-Object System.Drawing.Bitmap ($cw * $Cols + 8 * ($Cols - 1)), (($ch + 34) * $rows)
$g = [System.Drawing.Graphics]::FromImage($sheet)
$g.Clear([System.Drawing.Color]::FromArgb(40,40,40))
$font = New-Object System.Drawing.Font 'Segoe UI', 16, ([System.Drawing.FontStyle]::Bold)
$pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(150, 0, 255, 255)), 1
for ($i = 0; $i -lt $n; $i++) {
  $a = $Angles[$i]
  $tile = New-Object System.Drawing.Bitmap $cw, $ch
  $t = [System.Drawing.Graphics]::FromImage($tile)
  $t.InterpolationMode = 'HighQualityBicubic'
  # map frame centre -> rotate -> place region top-left at 0,0
  $t.ScaleTransform($scale, $scale)
  $t.TranslateTransform(-$rx0, -$ry0)
  $t.TranslateTransform($sw / 2, $sh / 2)
  $t.RotateTransform($a)
  $t.DrawImage($src, -$sw / 2, -$sh / 2, $sw, $sh)
  $t.ResetTransform()
  for ($k = 1; $k -lt 12; $k++) { $x = [int]($cw * $k / 12); $t.DrawLine($pen, $x, 0, $x, $ch) }
  $t.Dispose()
  $c = $i % $Cols; $r = [math]::Floor($i / $Cols)
  $x0 = $c * ($cw + 8); $y0 = $r * ($ch + 34)
  $g.DrawImage($tile, $x0, $y0 + 34)
  $lab = if ($a -eq 0) { 'as is (0)' } elseif ($a -gt 0) { "+$a deg (clockwise)" } else { "$a deg (counter-clockwise)" }
  $g.DrawString($lab, $font, [System.Drawing.Brushes]::Yellow, $x0 + 4, $y0 + 4)
  $tile.Dispose()
}
$sheet.Save($Out, [System.Drawing.Imaging.ImageFormat]::Jpeg)
$g.Dispose(); $sheet.Dispose(); $src.Dispose()
"saved $Out"
