# lfit.ps1: fit a straight edge (pole, roofline, horizon) near the line x0,y0 -> x1,y1 (fractions of the frame).
# Prints its angle in degrees: more reliable than measure.ps1 tilt for one known edge.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File lfit.ps1 <file> x0 y0 x1 y1 [-Band 12]
param([string]$File,[double]$x0,[double]$y0,[double]$x1,[double]$y1,[int]$Band=12)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @"
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class LF {
  public static string Fit(string path,double fx0,double fy0,double fx1,double fy1,int band){
    Bitmap bmp=new Bitmap(path); int w=bmp.Width,h=bmp.Height; var d=bmp.LockBits(new Rectangle(0,0,w,h),ImageLockMode.ReadOnly,PixelFormat.Format24bppRgb);
    byte[] b=new byte[d.Stride*h]; Marshal.Copy(d.Scan0,b,0,b.Length); bmp.UnlockBits(d); int st=d.Stride;
    Func<int,int,double> L=(x,y)=>{ x=Math.Max(0,Math.Min(w-1,x)); y=Math.Max(0,Math.Min(h-1,y)); int i=y*st+x*3; return 0.114*b[i]+0.587*b[i+1]+0.299*b[i+2]; };
    double X0=fx0*w,Y0=fy0*h,X1=fx1*w,Y1=fy1*h; bool horiz=Math.Abs(X1-X0)>=Math.Abs(Y1-Y0);
    var pts=new List<double[]>(); int n=(int)(horiz?Math.Abs(X1-X0):Math.Abs(Y1-Y0));
    for(int k=0;k<n;k+=2){ double t=(double)k/n; double px=X0+(X1-X0)*t, py=Y0+(Y1-Y0)*t; double best=0; int bo=0;
      for(int o=-band;o<=band;o++){ double g; if(horiz){ int x=(int)px,y=(int)py+o; g=Math.Abs((L(x-1,y+1)+2*L(x,y+1)+L(x+1,y+1))-(L(x-1,y-1)+2*L(x,y-1)+L(x+1,y-1))); } else { int x=(int)px+o,y=(int)py; g=Math.Abs((L(x+1,y-1)+2*L(x+1,y)+L(x+1,y+1))-(L(x-1,y-1)+2*L(x-1,y)+L(x-1,y+1))); }
        if(g>best){best=g;bo=o;} }
      if(best>150){ if(horiz) pts.Add(new double[]{px,py+bo}); else pts.Add(new double[]{px+bo,py}); } }
    if(pts.Count<20) return "too few points "+pts.Count;
    double slope=0,ic=0; for(int it=0;it<4;it++){ double sa=0,sb=0,saa=0,sab=0; int m=0; foreach(var p in pts){ double u=horiz?p[0]:p[1], v=horiz?p[1]:p[0]; if(it>0 && Math.Abs(v-(slope*u+ic))>2.5) continue; sa+=u;sb+=v;saa+=u*u;sab+=u*v;m++; }
      slope=(m*sab-sa*sb)/(m*saa-sa*sa); ic=(sb-slope*sa)/m; if(it==3) {
        // count inliers
        int inl=0; foreach(var p in pts){ double u=horiz?p[0]:p[1], v=horiz?p[1]:p[0]; if(Math.Abs(v-(slope*u+ic))<=2.5) inl++; }
        double ang=Math.Atan(slope)*180/Math.PI; return String.Format("{0} slope_deg={1:F2} inliers={2}/{3}", horiz?"horizontal(y down+ = descends right)":"vertical(+ = bottom moves right i.e. top leans left)", ang, inl, pts.Count); } }
    return "?"; } }
"@
[LF]::Fit($File,$x0,$y0,$x1,$y1,$Band)
