# sbs.ps1: labelled BEFORE | AFTER side-by-side of one region, at most -MaxW px wide (for phones).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File sbs.ps1 -Before a.jpg -After b.jpg -Region x0,x1,y0,y1 -Out out.jpg
param([string]$Before,[string]$After,[string]$Region,[string]$Out,[int]$MaxW=1600)
Add-Type -AssemblyName System.Drawing
$r=$Region -split ',' | % { [double]::Parse($_,[Globalization.CultureInfo]::InvariantCulture) }
$a=[System.Drawing.Image]::FromFile($Before); $b=[System.Drawing.Image]::FromFile($After)
function Rc($im){ New-Object System.Drawing.Rectangle ([int]($r[0]*$im.Width)),([int]($r[2]*$im.Height)),([int](($r[1]-$r[0])*$im.Width)),([int](($r[3]-$r[2])*$im.Height)) }
$ra=Rc $a; $rb=Rc $b
$cw=[int](($MaxW-8)/2); $sc=$cw/$ra.Width; if($sc -gt 1){$sc=1; $cw=$ra.Width}; $ch=[int]($ra.Height*$sc)
$o=New-Object System.Drawing.Bitmap (2*$cw+8),$ch; $g=[System.Drawing.Graphics]::FromImage($o); $g.Clear([System.Drawing.Color]::White)
$g.InterpolationMode='HighQualityBicubic'
$g.DrawImage($a,(New-Object System.Drawing.Rectangle 0,0,$cw,$ch),$ra,'Pixel')
$g.DrawImage($b,(New-Object System.Drawing.Rectangle ($cw+8),0,$cw,$ch),$rb,'Pixel')
$f=New-Object System.Drawing.Font 'Arial',([single]18)
$g.DrawString('BEFORE',$f,[System.Drawing.Brushes]::Yellow,6,6); $g.DrawString('AFTER',$f,[System.Drawing.Brushes]::Yellow,($cw+14),6)
$o.Save($Out,[System.Drawing.Imaging.ImageFormat]::Jpeg); "saved $($o.Width)x$($o.Height)"
