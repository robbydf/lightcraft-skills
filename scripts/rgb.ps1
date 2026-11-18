# rgb.ps1: mean R/G/B of a region (x0,x1,y0,y1 as fractions), for colour checks.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File rgb.ps1 <file> x0,x1,y0,y1
param([string]$File,[string]$Region)
Add-Type -AssemblyName System.Drawing
$r=$Region -split ',' | % { [double]::Parse($_,[Globalization.CultureInfo]::InvariantCulture) }
$bmp=New-Object System.Drawing.Bitmap $File; $w=$bmp.Width;$h=$bmp.Height
$x0=[int]($r[0]*$w);$x1=[int]($r[1]*$w);$y0=[int]($r[2]*$h);$y1=[int]($r[3]*$h)
$sr=0;$sg=0;$sb=0;$n=0
for($y=$y0;$y -lt $y1;$y+=2){for($x=$x0;$x -lt $x1;$x+=2){$c=$bmp.GetPixel($x,$y);$sr+=$c.R;$sg+=$c.G;$sb+=$c.B;$n++}}
"{0:F1}/{1:F1}/{2:F1}" -f ($sr/$n),($sg/$n),($sb/$n)
