# Measures JPEG/PNG renders exported from LightCraft (no Python packages needed).
#   sharp : Laplacian variance (higher = sharper). Noise inflates it: rank frames of ONE burst only,
#           all in the same develop state, and confirm the winner with crops.
#   tilt  : median lean of strong near-vertical edges (deg, + = top leans right) and median slope of
#           near-horizontal edges. Trust it only when n >= ~2000; otherwise widen the region.
#   mean  : mean luma 0..255 of the region (subject vs background brightness).
#   clip  : % of pixels in the region with any RGB channel at 255 (blown) and with all channels at 0 (crushed).
#   crops : stacks the same region of several files into one PNG (-Out) for side-by-side viewing.
#   sheet : contact sheet: several whole frames tiled -Cols across (default 3), each -Tile px wide
#           (default 600) and labelled with its file name, into one PNG (-Out). Up to 9 per sheet
#           reads well: 25 frames in 3 Reads.
#   batch : one file listing measurements, one per line: <image>|x0,x1,y0,y1[|label]. Prints mean,
#           blown and crushed for every line in one PowerShell start (before/after on many photos).
#   grid  : one file; draws labelled coordinate lines over the region (every 0.01, labels every 0.05)
#           and writes a PNG (-Out), for reading guide / brush coordinates.
# Usage (PowerShell):  & measure.ps1 sharp a.jpg b.jpg -Region 0.15,0.85,0.15,0.70
#                      & measure.ps1 sharp (Get-ChildItem dir\*.jpg).FullName
# Usage (Bash/-File):  powershell -NoProfile -ExecutionPolicy Bypass -File measure.ps1 tilt dir/*.jpg -Region 0.1,0.9,0.05,0.72
# Region = x0,x1,y0,y1 as fractions of the frame (0 <= x0 < x1 <= 1, 0 <= y0 < y1 <= 1).
param(
    [Parameter(Mandatory = $true, Position = 0)][ValidateSet("sharp", "tilt", "mean", "clip", "crops", "sheet", "batch", "grid")][string]$Mode,
    [Parameter(Mandatory = $true, Position = 1, ValueFromRemainingArguments = $true)][object[]]$Files,
    $Region = $null,   # a string "a,b,c,d" (powershell -File) or an array (& measure.ps1)
    [string]$Out = "",
    [int]$Cols = 3,
    [int]$Tile = 600
)
$ErrorActionPreference = "Stop"

# Region -> $Rg (double[]). PowerShell names are case-insensitive: never name another variable $rg.
$Rg = if ($Region) { @((@($Region) -join ',') -split '[,\s]+' | Where-Object { $_ } | ForEach-Object { [double]::Parse($_, [Globalization.CultureInfo]::InvariantCulture) }) } else { @() }
if ($Rg.Count -and ($Rg.Count -ne 4 -or $Rg[0] -ge $Rg[1] -or $Rg[2] -ge $Rg[3] -or @($Rg | Where-Object { $_ -lt 0 -or $_ -gt 1 }).Count)) {
    throw "Region must be x0,x1,y0,y1 with 0<=x0<x1<=1 and 0<=y0<y1<=1 (got: $($Rg -join ','))"
}
# Files: accept arrays, wildcards and relative paths; fail loudly on a missing file.
$Files = @($Files | ForEach-Object { $_ } | ForEach-Object {
        $m = @(Resolve-Path -Path "$_" -ErrorAction SilentlyContinue)
        if (-not $m.Count) { throw "missing file: $_" }
        $m.ProviderPath })
# Bitmap.Save resolves relative paths against the process folder, so make -Out absolute.
if ($Out) { $Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out) }

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @"
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class LcMeasure {
  static double[] Gray(string path, out int w, out int h) {
    using (var bmp = new Bitmap(path)) {
      w=bmp.Width; h=bmp.Height; var d=bmp.LockBits(new Rectangle(0,0,w,h),ImageLockMode.ReadOnly,PixelFormat.Format24bppRgb);
      byte[] b=new byte[d.Stride*h]; Marshal.Copy(d.Scan0,b,0,b.Length); bmp.UnlockBits(d);
      var g=new double[w*h]; for(int y=0;y<h;y++) for(int x=0;x<w;x++){int i=y*d.Stride+x*3; g[y*w+x]=0.114*b[i]+0.587*b[i+1]+0.299*b[i+2];}
      return g; } }
  public static string Sharp(string path,double x0,double x1,double y0,double y1){
    int w,h; var g=Gray(path,out w,out h); double s=0,s2=0; long n=0;
    for(int y=Math.Max(1,(int)(y0*h));y<Math.Min(h-1,(int)(y1*h));y++) for(int x=Math.Max(1,(int)(x0*w));x<Math.Min(w-1,(int)(x1*w));x++){
      double l=4*g[y*w+x]-g[y*w+x-1]-g[y*w+x+1]-g[(y-1)*w+x]-g[(y+1)*w+x]; s+=l; s2+=l*l; n++; }
    if(n==0) return "sharp=NA (region too small)";
    return String.Format("sharp={0:F0}", s2/n-(s/n)*(s/n)); }
  public static string Mean(string path,double x0,double x1,double y0,double y1){
    int w,h; var g=Gray(path,out w,out h); double s=0; long n=0;
    for(int y=(int)(y0*h);y<Math.Min(h,(int)(y1*h));y++) for(int x=(int)(x0*w);x<Math.Min(w,(int)(x1*w));x++){ s+=g[y*w+x]; n++; }
    if(n==0) return "mean=NA (region too small)";
    return String.Format("mean={0:F1}", s/n); }
  public static string Clip(string path,double x0,double x1,double y0,double y1){
    using (var bmp = new Bitmap(path)) {
      int w=bmp.Width, h=bmp.Height; var d=bmp.LockBits(new Rectangle(0,0,w,h),ImageLockMode.ReadOnly,PixelFormat.Format24bppRgb);
      byte[] b=new byte[d.Stride*h]; Marshal.Copy(d.Scan0,b,0,b.Length); bmp.UnlockBits(d);
      long n=0, hi=0, lo=0;
      for(int y=(int)(y0*h);y<Math.Min(h,(int)(y1*h));y++) for(int x=(int)(x0*w);x<Math.Min(w,(int)(x1*w));x++){
        int i=y*d.Stride+x*3; n++;
        if(b[i]==255||b[i+1]==255||b[i+2]==255) hi++;
        if(b[i]==0&&b[i+1]==0&&b[i+2]==0) lo++; }
      if(n==0) return "clip=NA (region too small)";
      return String.Format(System.Globalization.CultureInfo.InvariantCulture,"blown={0:F2}% crushed={1:F2}%", 100.0*hi/n, 100.0*lo/n); } }
  public static string Tilt(string path,double x0,double x1,double y0,double y1){
    int w,h; var g=Gray(path,out w,out h); var v=new List<double>(); var hz=new List<double>();
    Func<int,int,double> L=(x,y)=>g[y*w+x];
    for(int y=Math.Max(1,(int)(y0*h));y<Math.Min(h-1,(int)(y1*h));y++) for(int x=Math.Max(1,(int)(x0*w));x<Math.Min(w-1,(int)(x1*w));x++){
      double gx=(L(x+1,y-1)+2*L(x+1,y)+L(x+1,y+1))-(L(x-1,y-1)+2*L(x-1,y)+L(x-1,y+1));
      double gy=(L(x-1,y+1)+2*L(x,y+1)+L(x+1,y+1))-(L(x-1,y-1)+2*L(x,y-1)+L(x+1,y-1));
      if(Math.Sqrt(gx*gx+gy*gy)<120) continue;
      double a=Math.Atan2(gy,gx)*180/Math.PI;
      double av=a; if(av>90) av-=180; if(av<-90) av+=180; if(Math.Abs(av)<12) v.Add(-av);
      double ah=a-90; if(ah>90) ah-=180; if(ah<-90) ah+=180; if(Math.Abs(ah)<12) hz.Add(ah); }
    v.Sort(); hz.Sort();
    string vt = v.Count>0 ? String.Format("{0:F2}deg", v[v.Count/2]) : "NA";
    string ht = hz.Count>0 ? String.Format("{0:F2}deg", hz[hz.Count/2]) : "NA";
    return String.Format("vertical_tilt={0} (n={1}) horizontal_slope={2} (n={3})", vt, v.Count, ht, hz.Count); }
}
"@
function Need-Out { if (-not $Out) { throw "$Mode needs -Out file.png" } ; if ($Out -notmatch '\.png$') { throw "-Out must end in .png" } }

switch ($Mode) {
    "sharp" { if (-not $Rg.Count) { $Rg = 0.15, 0.85, 0.15, 0.70 }
        foreach ($f in $Files) { "{0}  {1}" -f (Split-Path $f -Leaf), [LcMeasure]::Sharp($f, $Rg[0], $Rg[1], $Rg[2], $Rg[3]) } }
    "tilt" { if (-not $Rg.Count) { $Rg = 0.1, 0.9, 0.05, 0.72 }
        foreach ($f in $Files) { "{0}  {1}" -f (Split-Path $f -Leaf), [LcMeasure]::Tilt($f, $Rg[0], $Rg[1], $Rg[2], $Rg[3]) } }
    "mean" { if (-not $Rg.Count) { throw "mean needs -Region x0,x1,y0,y1" }
        foreach ($f in $Files) { "{0}  {1}" -f (Split-Path $f -Leaf), [LcMeasure]::Mean($f, $Rg[0], $Rg[1], $Rg[2], $Rg[3]) } }
    "clip" { if (-not $Rg.Count) { $Rg = 0, 1, 0, 1 }
        foreach ($f in $Files) { "{0}  {1}" -f (Split-Path $f -Leaf), [LcMeasure]::Clip($f, $Rg[0], $Rg[1], $Rg[2], $Rg[3]) } }
    "crops" {
        if ($Rg.Count -ne 4) { throw "crops needs -Region x0,x1,y0,y1" }; Need-Out
        # More than 4 crops are downscaled when viewed and fine detail becomes unreadable.
        if ($Files.Count -gt 4) { throw "crops takes at most 4 files (got $($Files.Count)); split them into sheets of 4" }
        $first = [System.Drawing.Image]::FromFile($Files[0]); $W = $first.Width; $H = $first.Height; $first.Dispose()
        $cw = [int](($Rg[1] - $Rg[0]) * $W); $ch = [int](($Rg[3] - $Rg[2]) * $H)
        $outBmp = New-Object System.Drawing.Bitmap $cw, ($ch * $Files.Count); $g = [System.Drawing.Graphics]::FromImage($outBmp)
        $font = New-Object System.Drawing.Font "Arial", 16; $i = 0
        foreach ($f in $Files) { $src = [System.Drawing.Image]::FromFile($f)
            $rect = New-Object System.Drawing.Rectangle ([int]($Rg[0] * $src.Width)), ([int]($Rg[2] * $src.Height)), $cw, $ch
            $g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, ($i * $ch), $cw, $ch), $rect, [System.Drawing.GraphicsUnit]::Pixel)
            $g.DrawString((Split-Path $f -Leaf), $font, [System.Drawing.Brushes]::Yellow, 5, ($i * $ch + 5)); $src.Dispose(); $i++ }
        $outBmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $font.Dispose(); $outBmp.Dispose(); "saved $Out" }
    "sheet" {
        Need-Out; if ($Files.Count -gt 12) { throw "sheet takes at most 12 files (got $($Files.Count)); 9 per sheet reads best" }
        $n = $Files.Count; $c = [math]::Min($Cols, $n); $r = [math]::Ceiling($n / $c)
        $th = [int]($Tile * 2 / 3)   # 3:2 cells; portrait frames are fitted inside (narrower), not stretched
        $outBmp = New-Object System.Drawing.Bitmap ($c * $Tile), ($r * $th); $g = [System.Drawing.Graphics]::FromImage($outBmp)
        $g.Clear([System.Drawing.Color]::Black); $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $font = New-Object System.Drawing.Font "Arial", 14, ([System.Drawing.FontStyle]::Bold); $i = 0
        foreach ($f in $Files) { $src = [System.Drawing.Image]::FromFile($f)
            $tw = $Tile; $tht = [int]($Tile * $src.Height / $src.Width); if ($tht -gt $th) { $tht = $th; $tw = [int]($th * $src.Width / $src.Height) }
            $x = ($i % $c) * $Tile + [int](($Tile - $tw) / 2); $y = [math]::Floor($i / $c) * $th + [int](($th - $tht) / 2)
            $g.DrawImage($src, (New-Object System.Drawing.Rectangle $x, $y, $tw, $tht)); $src.Dispose()
            $lab = [IO.Path]::GetFileNameWithoutExtension($f); $sz = $g.MeasureString($lab, $font)
            $g.FillRectangle([System.Drawing.Brushes]::Black, [float]($x + 3), [float]($y + 3), $sz.Width, $sz.Height)
            $g.DrawString($lab, $font, [System.Drawing.Brushes]::Yellow, [float]($x + 3), [float]($y + 3)); $i++ }
        $outBmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $font.Dispose(); $outBmp.Dispose(); "saved $Out ($n frames, $c x $r)" }
    "batch" {
        if ($Files.Count -ne 1) { throw "batch takes one list file: <image>|x0,x1,y0,y1[|label] per line" }
        $base = Split-Path $Files[0] -Parent; $ln = 0
        foreach ($line in Get-Content -LiteralPath $Files[0]) { $ln++; $line = $line.Trim(); if (-not $line -or $line.StartsWith("#")) { continue }
            $p = $line -split '\|'; if ($p.Count -lt 2) { "line ${ln}: need <image>|x0,x1,y0,y1[|label]"; continue }
            $img = $p[0].Trim(); if (-not [IO.Path]::IsPathRooted($img)) { $img = Join-Path $base $img }
            if (-not (Test-Path -LiteralPath $img)) { "line ${ln}: missing file $img"; continue }
            $b = @($p[1] -split '[,\s]+' | Where-Object { $_ } | ForEach-Object { [double]::Parse($_, [Globalization.CultureInfo]::InvariantCulture) })
            if ($b.Count -ne 4 -or $b[0] -ge $b[1] -or $b[2] -ge $b[3]) { "line ${ln}: bad region $($p[1])"; continue }
            $lab = if ($p.Count -gt 2) { $p[2].Trim() } else { Split-Path $img -Leaf }
            "{0}  {1} {2}  [{3}]" -f $lab, [LcMeasure]::Mean($img, $b[0], $b[1], $b[2], $b[3]), [LcMeasure]::Clip($img, $b[0], $b[1], $b[2], $b[3]), ($b -join ',') } }
    "grid" {
        if ($Files.Count -ne 1) { throw "grid takes exactly one file" }; Need-Out
        if (-not $Rg.Count) { $Rg = 0, 1, 0, 1 }
        $src = [System.Drawing.Image]::FromFile($Files[0]); $W = $src.Width; $H = $src.Height
        $rect = New-Object System.Drawing.Rectangle ([int]($Rg[0] * $W)), ([int]($Rg[2] * $H)), ([int](($Rg[1] - $Rg[0]) * $W)), ([int](($Rg[3] - $Rg[2]) * $H))
        $bmp = New-Object System.Drawing.Bitmap $rect.Width, $rect.Height; $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, $rect.Width, $rect.Height), $rect, [System.Drawing.GraphicsUnit]::Pixel); $src.Dispose()
        $thin = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(90, 0, 255, 255)), 1
        $bold = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(200, 0, 255, 255)), 1
        $font = New-Object System.Drawing.Font "Arial", 9
        for ($v = [math]::Ceiling($Rg[0] * 100); $v -le [math]::Floor($Rg[1] * 100); $v++) { $x = ($v / 100 - $Rg[0]) * $W
            $g.DrawLine($(if ($v % 5) { $thin } else { $bold }), [float]$x, 0, [float]$x, $rect.Height)
            if (-not ($v % 5)) { $g.DrawString(("{0:N2}" -f ($v / 100)), $font, [System.Drawing.Brushes]::Yellow, [float]($x + 1), 2) } }
        for ($v = [math]::Ceiling($Rg[2] * 100); $v -le [math]::Floor($Rg[3] * 100); $v++) { $y = ($v / 100 - $Rg[2]) * $H
            $g.DrawLine($(if ($v % 5) { $thin } else { $bold }), 0, [float]$y, $rect.Width, [float]$y)
            if (-not ($v % 5)) { $g.DrawString(("{0:N2}" -f ($v / 100)), $font, [System.Drawing.Brushes]::Yellow, 2, [float]($y + 1)) } }
        $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose(); "saved $Out" }
}
