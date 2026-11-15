#version 300 es
// United Games — "Le calme avant la tempête" — scène procédurale (raymarching)
precision highp float;
out vec4 fragColor;

uniform vec2 uRes;
uniform float uTime;
uniform vec3 uCamPos, uCamTgt;
uniform float uFov, uRoll;
uniform float uFlash, uBolt;
uniform vec2 uBoltPts[24];
uniform float uQ, uFog, uExposure;
uniform float uCarX, uCarZ, uWheelAng;

#define ROAD_HW 7.0
#define WALK 10.0
#define CELL 16.0
#define ZEND 260.0
#define PI 3.14159265

// ---------------------------------------------------------------- utils
float hash11(float p){ p=fract(p*0.1031); p*=p+33.33; p*=p+p; return fract(p); }
float hash21(vec2 p){ vec3 p3=fract(vec3(p.xyx)*0.1031); p3+=dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
float hash31(vec3 p3){ p3=fract(p3*0.1031); p3+=dot(p3,p3.zyx+31.32); return fract((p3.x+p3.y)*p3.z); }
float noise2(vec2 x){ vec2 i=floor(x), f=fract(x); f=f*f*(3.-2.*f);
  return mix(mix(hash21(i),hash21(i+vec2(1,0)),f.x), mix(hash21(i+vec2(0,1)),hash21(i+vec2(1,1)),f.x), f.y); }
float noise3(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.-2.*f);
  float a=hash31(i), b=hash31(i+vec3(1,0,0)), c=hash31(i+vec3(0,1,0)), d=hash31(i+vec3(1,1,0));
  float e=hash31(i+vec3(0,0,1)), g=hash31(i+vec3(1,0,1)), h=hash31(i+vec3(0,1,1)), k=hash31(i+vec3(1,1,1));
  return mix(mix(mix(a,b,f.x),mix(c,d,f.x),f.y), mix(mix(e,g,f.x),mix(h,k,f.x),f.y), f.z); }
float fbm2(vec2 p){ float s=0., a=0.5; for(int i=0;i<5;i++){ s+=a*noise2(p); p=p*2.03+vec2(1.7,9.2); a*=0.5; } return s; }

float sdBox(vec3 p, vec3 b){ vec3 q=abs(p)-b; return length(max(q,0.))+min(max(q.x,max(q.y,q.z)),0.); }
float sdRBox(vec3 p, vec3 b, float r){ vec3 q=abs(p)-b+r; return length(max(q,0.))+min(max(q.x,max(q.y,q.z)),0.)-r; }
float smin(float a, float b, float k){ float h=clamp(0.5+0.5*(b-a)/k,0.,1.); return mix(b,a,h)-k*h*(1.-h); }
float sdCylX(vec3 p, float r, float hw){ vec2 d=abs(vec2(length(p.yz),p.x))-vec2(r,hw); return min(max(d.x,d.y),0.)+length(max(d,0.)); }

// ---------------------------------------------------------------- city layout
void bparams(float s, float k, out float h, out float hz, out float top){
  float r1=hash21(vec2(k*1.31+0.7, s*7.1+1.3));
  float r2=hash21(vec2(k*1.7+3.1, s*3.3+0.2));
  h = 24.0 + 100.0*r1*r1;
  hz = 6.2 + 1.2*r2;
  top = hash21(vec2(k+11.0, s*5.0));
}

float buildingCell(vec3 p, float s, float k){
  if(k*CELL > ZEND-4.0) return 1e5;
  float h,hz,top; bparams(s,k,h,hz,top);
  float u = s*p.x - WALK;
  float lz = p.z - (k+0.5)*CELL;
  float d = sdBox(vec3(u-20.0, p.y-h*0.5, lz), vec3(20.0, h*0.5, hz));
  if(top>0.5) d = min(d, sdBox(vec3(u-23.0, p.y-h-5.0, lz), vec3(14.0, 5.0, hz-2.0)));
  return d;
}

float buildings(vec3 p, out float side){
  float s = p.x>0.0 ? 1.0 : -1.0;
  side = s;
  float k = floor(p.z/CELL);
  float lz = p.z - (k+0.5)*CELL;
  float d = buildingCell(p, s, k);
  d = min(d, buildingCell(p, s, k + (lz>0.0?1.0:-1.0)));
  return d;
}

float tower(vec3 p){
  float d = sdBox(p-vec3(0,140,ZEND+30.0), vec3(42,140,30));
  d = min(d, sdBox(p-vec3(0,296,ZEND+30.0), vec3(26,16,20)));
  d = min(d, sdBox(p-vec3(0,330,ZEND+30.0), vec3(0.6,22,0.6)));
  // tours de fond derrière
  d = min(d, sdBox(p-vec3(-70,95,ZEND+60.0), vec3(25,95,25)));
  d = min(d, sdBox(p-vec3(75,120,ZEND+50.0), vec3(28,120,22)));
  return d;
}

// mobilier : lampadaires (côtés alternés)
float lamps(vec3 p){
  float k = floor(p.z/40.0);
  float s = mod(k,2.0)<1.0 ? 1.0 : -1.0;
  float lz = p.z-(k+0.5)*40.0;
  vec3 q = vec3(s*p.x, p.y, lz);
  float d = length(q.xz-vec2(7.8,0.0))-0.1;
  d = max(d, q.y-7.6);
  d = min(d, sdBox(q-vec3(7.0,7.55,0), vec3(0.85,0.05,0.06)));
  d = min(d, sdBox(q-vec3(6.15,7.45,0), vec3(0.32,0.07,0.16)));
  return d;
}

// enseignes néon verticales (sans texte)
float signs(vec3 p, out vec3 sl){
  float s = p.x>0.0 ? 1.0 : -1.0;
  float k = floor(p.z/CELL);
  float r = hash21(vec2(k*3.7, s*1.9+4.0));
  sl = vec3(0);
  if(r<0.45 || k*CELL>ZEND-8.0) return 1e5;
  float h,hz,top; bparams(s,k,h,hz,top);
  float off = (hash21(vec2(k, s+9.0))-0.5)*2.0*(hz-1.5);
  vec3 q = vec3(s*p.x - WALK, p.y, p.z-(k+0.5)*CELL-off);
  float hh = 1.4+1.4*hash21(vec2(k,s+2.0));
  sl = vec3(q.x+0.75, q.y-(5.2+hh), q.z);
  sl.y /= hh;
  return sdBox(q-vec3(-0.75,5.2+hh,0.0), vec3(0.7,hh,0.07));
}

// voiture noire
float gMat;
float car(vec3 p){
  vec3 q = p - vec3(uCarX, 0.0, uCarZ);
  float bb = length(q-vec3(0,0.7,0)) - 3.2;
  if(bb>0.5) return bb;
  vec3 b = q - vec3(0,0.6,0);
  b.y += 0.10*smoothstep(1.0,2.4,b.z);   // capot plongeant
  float body = sdRBox(b, vec3(0.96,0.30,2.38), 0.2);
  vec3 c = q - vec3(0,1.06,-0.2);
  c.z *= 1.0 + c.y*1.6;
  c.x *= 1.0 + c.y*0.55;
  float cabin = sdRBox(c, vec3(0.78,0.24,1.12), 0.18);
  float d = smin(body, cabin, 0.12);
  float arch = length(vec2(q.y-0.36, abs(q.z)-1.45)) - 0.44;
  d = max(d, -max(arch, 0.55-abs(q.x)));
  vec3 wq = vec3(abs(q.x)-0.84, q.y-0.36, abs(q.z)-1.45);
  float wheel = sdCylX(wq, 0.34, 0.12) - 0.02;
  if(wheel<d){ gMat = 7.0; return wheel; }
  gMat = (q.y>0.94 && abs(c.x)<0.95) ? 6.0 : 5.0;
  return d;
}

float map(vec3 p){
  float side;
  float d = p.y; gMat = 1.0;
  float sw = sdBox(vec3(abs(p.x)-8.5, p.y-0.09, 0.0), vec3(1.5,0.09,1e4));
  if(sw<d){ d=sw; gMat=2.0; }
  float b = buildings(p, side);
  if(b<d){ d=b; gMat=3.0; }
  float tw = tower(p);
  if(tw<d){ d=tw; gMat=4.0; }
  if(abs(p.x)>5.5 && abs(p.x)<9.0){ float l=lamps(p); if(l<d){ d=l; gMat=9.0; } }
  if(abs(p.x)>8.0 && abs(p.x)<10.5 && p.y<12.0){ vec3 sl; float sg=signs(p,sl); if(sg<d){ d=sg; gMat=10.0; } }
  float m = gMat;
  float cr = car(p);
  if(cr<d){ d=cr; } else gMat = m;
  return d;
}

vec3 calcNormal(vec3 p){
  const vec2 e = vec2(1,-1)*0.0015;
  return normalize(e.xyy*map(p+e.xyy)+e.yyx*map(p+e.yyx)+e.yxy*map(p+e.yxy)+e.xxx*map(p+e.xxx));
}

float trace(vec3 ro, vec3 rd, float tmax, int steps, out float mat){
  float t = 0.02; mat = 0.0;
  for(int i=0;i<200;i++){
    if(i>=steps) break;
    vec3 p = ro+rd*t;
    float d = map(p);
    if(abs(d)<0.0012*t+0.0008){ mat=gMat; return t; }
    t += d*0.82;
    if(t>tmax) break;
  }
  return -1.0;
}

// ---------------------------------------------------------------- lights
const vec3 NEON_RED = vec3(1.0,0.06,0.10);
const vec3 LAMP_COL = vec3(0.70,0.82,1.0);
const vec3 FLASH_COL = vec3(0.75,0.80,1.0);

vec3 neonColor(float s, float k){
  float r = hash21(vec2(k*5.1, s+3.0));
  return r<0.75 ? NEON_RED : vec3(1.0,0.12,0.45);
}
float neonFlicker(float s, float k){
  float r = hash21(vec2(k*2.3, s+7.0));
  if(r>0.82){ float f = step(0.35, noise2(vec2(uTime*14.0, k*3.0+s))); return 0.25+0.75*f; }
  if(r>0.72) return 0.15;   // enseigne mourante
  return 0.92+0.08*noise2(vec2(uTime*30.0,k));
}

vec3 qCenter(){ return vec3(0.0, 125.0, ZEND); }

// irradiance des lumières locales en p (n = normale, ou 0 pour un milieu)
vec3 localLights(vec3 p, vec3 n){
  vec3 L = vec3(0);
  bool medium = dot(n,n)<0.5;
  // néons (cellule courante et voisines, deux côtés)
  float k0 = floor(p.z/CELL);
  for(int si=0; si<2; si++){
    float s = si==0 ? -1.0 : 1.0;
    for(int j=-1;j<=1;j++){
      float k = k0+float(j);
      float r = hash21(vec2(k*3.7, s*1.9+4.0));
      if(r<0.45 || k*CELL>ZEND-8.0) continue;
      float h,hz,top; bparams(s,k,h,hz,top);
      float off = (hash21(vec2(k, s+9.0))-0.5)*2.0*(hz-1.5);
      float hh = 1.4+1.4*hash21(vec2(k,s+2.0));
      vec3 lp = vec3(s*(WALK-0.75), 5.2+hh, (k+0.5)*CELL+off);
      vec3 dv = lp-p; float d2 = dot(dv,dv);
      float ndl = medium ? 1.0 : max(dot(n, dv*inversesqrt(d2)),0.0)*0.85+0.15;
      L += neonColor(s,k)*neonFlicker(s,k) * 9.0*hh * ndl / (1.0+d2);
    }
  }
  // bandeaux néon des rez-de-chaussée
  // lampadaires
  float lk = floor(p.z/40.0);
  for(int j=-1;j<=1;j++){
    float k = lk+float(j);
    float s = mod(k,2.0)<1.0 ? 1.0 : -1.0;
    float hs = hash11(k*7.7+1.0);
    float on = hs<0.3 ? 0.0 : (hs<0.5 ? step(0.45, noise2(vec2(uTime*9.0,k))) : 1.0);
    if(on<=0.0) continue;
    vec3 lp = vec3(s*6.15, 7.3, (k+0.5)*40.0);
    vec3 dv = lp-p; float d2=dot(dv,dv); vec3 l = dv*inversesqrt(d2);
    float cone = smoothstep(0.35, 0.85, -l.y);
    float ndl = medium ? 1.0 : max(dot(n,l),0.0);
    L += LAMP_COL * on * 30.0 * cone * ndl / (1.0+d2);
  }
  // phares de la voiture
  vec3 cp = vec3(uCarX, 0.0, uCarZ);
  for(int i=0;i<2;i++){
    vec3 lp = cp + vec3(i==0?-0.66:0.66, 0.66, 2.45);
    vec3 dv = p-lp; float d2=dot(dv,dv); vec3 l = dv*inversesqrt(d2);
    vec3 dir = normalize(vec3(0.0,-0.12,1.0));
    float cs = dot(l,dir);
    float cone = smoothstep(0.86, 0.97, cs) + 0.15*smoothstep(0.6,0.9,cs);
    float ndl = medium ? 1.0 : max(dot(n,-l),0.0);
    L += vec3(1.0,0.93,0.82) * (medium?30.0:90.0) * cone * ndl / (0.5+d2);
  }
  // feux arrière
  {
    vec3 lp = cp + vec3(0,0.8,-2.5);
    vec3 dv = lp-p; float d2=dot(dv,dv);
    float back = smoothstep(-0.2, 0.6, -(dv.z)*inversesqrt(d2));
    float ndl = medium ? 1.0 : max(dot(n,dv*inversesqrt(d2)),0.0);
    L += vec3(1.0,0.02,0.02)*3.5*back*ndl/(0.3+d2);
  }
  // point d'interrogation
  if(uQ>0.0){
    vec3 dv = qCenter()-p; float d2=dot(dv,dv);
    float ndl = medium ? 1.0 : max(dot(n,dv*inversesqrt(d2)),0.0)*0.8+0.2;
    L += NEON_RED * uQ * 380.0 * ndl / (2500.0+d2);
  }
  return L;
}

// ---------------------------------------------------------------- question mark (forme géométrique)
float sdQuestion(vec2 p){
  // unités : hauteur totale ~1, origine en bas au centre
  vec2 c = vec2(0.0, 0.66);
  float R = 0.22;
  vec2 q = p-c;
  float a = atan(q.y, q.x);
  float d;
  if(a < -PI*0.5){ // quart bas-gauche exclu
    d = min(length(q-vec2(0.0,-R)), length(q-vec2(-R,0.0)));
  } else d = abs(length(q)-R);
  // tige
  vec2 s0 = vec2(0.0, c.y-R), s1 = vec2(0.0, 0.27);
  vec2 pa = p-s1, ba = s0-s1; float h = clamp(dot(pa,ba)/dot(ba,ba),0.,1.);
  d = min(d, length(pa-ba*h));
  d -= 0.032;
  // point
  d = min(d, length(p-vec2(0.0,0.09))-0.07);
  return d;
}

// ---------------------------------------------------------------- sky
vec3 sky(vec3 rd){
  float el = rd.y;
  vec3 col = mix(vec3(0.018,0.016,0.02), vec3(0.006,0.008,0.014), smoothstep(0.0,0.5,el));
  // pollution lumineuse rougeâtre
  col += vec3(0.05,0.012,0.012)*exp(-max(el,0.0)*6.0);
  vec2 uv = rd.xz/max(rd.y,0.05);
  float cl = fbm2(uv*0.9 + vec2(uTime*0.03, uTime*0.012));
  float cl2 = fbm2(uv*2.3 - vec2(uTime*0.05, 0.0));
  float dens = smoothstep(0.35,0.85, cl*0.7+cl2*0.4);
  col *= 0.6+0.8*dens;
  // éclair dans les nuages
  float az = atan(rd.x, rd.z), elv = asin(clamp(rd.y,-1.0,1.0));
  float flashSpot = 0.5+0.5*smoothstep(1.2,0.0,abs(az-uBoltPts[0].x));
  col += FLASH_COL*uFlash*(0.25+1.6*dens*dens)*flashSpot*smoothstep(-0.1,0.3,el);
  if(uBolt>0.0){
    float d = 1e5;
    vec2 pp = vec2(az, elv);
    for(int i=0;i<23;i++){
      vec2 a=uBoltPts[i], b=uBoltPts[i+1];
      vec2 pa=pp-a, ba=b-a; float h=clamp(dot(pa,ba)/dot(ba,ba),0.,1.);
      d = min(d, length(pa-ba*h));
    }
    col += vec3(0.85,0.88,1.0)*uBolt*(9.0*exp(-d/0.0011) + 1.6*exp(-d/0.012) + 0.25*exp(-d/0.06));
  }
  return col;
}

// ---------------------------------------------------------------- shading
vec3 facadeEmission(vec3 p, vec3 n, float s, float k, float isTower, out float glass){
  glass = 0.0;
  vec3 e = vec3(0);
  float fx = abs(n.x)>0.5 ? p.z : p.x;
  if(isTower>0.5){
    // façade de verre sombre à ailettes verticales
    float fin = smoothstep(0.08,0.0,abs(fract(fx/3.0)-0.5)-0.44);
    float fl = smoothstep(0.06,0.0,abs(fract(p.y/4.0)-0.5)-0.46);
    glass = (1.0-fin)*(1.0-fl);
    // feu d'obstacle rouge clignotant au sommet
    return e;
  }
  vec2 wc = vec2(fx/2.7, (p.y-0.6)/3.5);
  vec2 id = floor(wc), f = fract(wc)-0.5;
  if(p.y>4.6){
    float win = step(abs(f.x),0.32)*step(abs(f.y),0.3);
    glass = win;
    float r = hash31(vec3(id, s*13.0+k));
    if(win>0.0 && r>0.9){
      float r2 = hash31(vec3(id+7.0, s+k));
      vec3 wcol = r2<0.65 ? vec3(1.0,0.55,0.25) : vec3(0.45,0.65,1.0);
      float fl = r2>0.85 ? (0.6+0.4*noise2(vec2(uTime*6.0, r*40.0))) : 1.0;
      float inner = 0.6+0.4*smoothstep(0.35,0.0,length(f*vec2(1.0,1.2)));
      e += wcol*fl*inner*(0.5+1.5*hash11(r*91.0))*0.9;
    }
  } else {
    // rez-de-chaussée : vitrines sombres + bandeau néon éventuel
    glass = step(abs(fract(fx/6.0)-0.5),0.42)*step(p.y,3.5)*step(0.4,p.y);
    float r = hash21(vec2(k*1.9+0.3, s*4.4));
    if(r>0.55 && abs(n.x)>0.5){
      float band = smoothstep(0.07,0.03,abs(p.y-3.9)) + 0.25*exp(-abs(p.y-3.9)*6.0);
      vec3 nc = neonColor(s,k+5.0)*neonFlicker(s,k+3.0);
      e += nc*band*1.6;
    }
  }
  return e;
}

vec3 envReflect(vec3 r){
  return sky(r)*0.8;
}

vec3 shade(vec3 p, vec3 n, vec3 rd, float mat, bool primary, out float refl, out vec3 rn){
  refl = 0.0; rn = n;
  vec3 alb = vec3(0.05);
  vec3 emi = vec3(0);
  float occ = 1.0;
  float spec = 0.0;
  if(mat<1.5){ // route mouillée
    float nz = noise2(p.xz*3.0)*0.5+noise2(p.xz*11.0)*0.5;
    alb = vec3(0.028+0.02*nz);
    // marquages
    float dash = step(fract(p.z/6.0),0.5)*step(abs(p.x),0.08);
    float edge = step(abs(abs(p.x)-6.6),0.07);
    float wear = smoothstep(0.25,0.6,noise2(p.xz*vec2(4.0,1.0)));
    alb = mix(alb, vec3(0.32,0.30,0.26), (dash+edge)*wear);
    float puddle = smoothstep(0.42,0.62, noise2(p.xz*vec2(0.18,0.11)+3.0)*0.7+noise2(p.xz*0.9)*0.3);
    // ondes de pluie
    vec2 g = p.xz/0.7; vec2 gi = floor(g), gf = fract(g)-0.5;
    float ph = fract(uTime*1.4 + hash21(gi));
    vec2 o = (vec2(hash21(gi+3.1),hash21(gi+7.7))-0.5)*0.5;
    float rr = length(gf-o);
    float ring = sin((rr-ph*0.45)*60.0)*exp(-abs(rr-ph*0.45)*25.0)*(1.0-ph);
    vec2 rgrad = (gf-o)/max(rr,1e-3)*ring*0.25;
    float rough = mix(0.16, 0.03, puddle);
    vec2 pert = vec2(noise2(p.xz*vec2(9.0,2.5))-0.5, noise2(p.xz*vec2(2.5,9.0)+5.0)-0.5)*rough*2.0;
    rn = normalize(vec3(pert.x+rgrad.x, 1.0, pert.y+rgrad.y));
    occ = 0.4;
    refl = mix(0.55, 1.0, puddle);
    alb *= mix(1.0, 0.35, puddle);
  } else if(mat<2.5){ // trottoir
    alb = vec3(0.06)*(0.8+0.4*noise2(p.xz*2.0));
    float tile = smoothstep(0.03,0.0,min(abs(fract(p.z/1.2)-0.5)-0.47, 1.0));
    alb *= 1.0-0.4*tile;
    rn = normalize(n+vec3(noise2(p.xz*7.0)-0.5,0.0,noise2(p.xz*7.0+3.0)-0.5)*0.25);
    refl = 0.35; occ = 0.45;
  } else if(mat<3.5 || (mat>3.5 && mat<4.5)){ // immeubles
    float isTower = mat>3.5 ? 1.0 : 0.0;
    float s = p.x>0.0?1.0:-1.0;
    float k = floor((p.z-n.z*0.01)/CELL);
    float glass;
    emi = facadeEmission(p, n, s, k, isTower, glass);
    float grime = noise2(vec2(p.z+p.x, p.y)*0.3)*0.6+noise2(vec2(p.z+p.x,p.y)*2.0)*0.4;
    alb = vec3(0.07,0.07,0.075)*(0.5+0.8*grime)*(0.7+0.6*hash21(vec2(k,s)));
    if(isTower>0.5) alb = vec3(0.03,0.032,0.036)*(0.7+0.5*grime);
    alb *= 1.0-0.75*glass;
    spec = glass;
    occ = clamp(0.25 + p.y/70.0, 0.0, 1.0);
    if(isTower>0.5){
      if(abs(n.z)>0.5 && n.z<0.0){
        vec2 qp = (vec2(-p.x, p.y) - vec2(0.0, 125.0-32.0))/64.0;
        float dq = sdQuestion(qp)*64.0;
        float core = smoothstep(0.9, 0.2, dq);
        float tube = exp(-max(dq,0.0)*0.9);
        float halo = exp(-max(dq,0.0)*0.12);
        emi += NEON_RED*uQ*(core*9.0 + tube*1.5 + halo*0.12);
        emi += vec3(1.0,0.45,0.4)*uQ*smoothstep(0.0,-1.2,dq)*4.0;
        // tube éteint visible sous l'éclair
        alb = mix(alb, vec3(0.12,0.05,0.05), core*(1.0-uQ));
      }
      float blink = step(0.5, fract(uTime*0.8));
      float dl = length(p-vec3(0,352,ZEND+30.0));
      emi += vec3(1.0,0.05,0.03)*blink*exp(-dl*0.6)*20.0;
    }
  } else if(mat<5.5){ // carrosserie noire
    alb = vec3(0.012);
    refl = 1.0; spec = 1.0;
    vec3 q = p - vec3(uCarX,0.0,uCarZ);
    // phares
    if(q.z>2.2 && abs(abs(q.x)-0.66)<0.22 && abs(q.y-0.66)<0.07) emi += vec3(1.0,0.95,0.88)*30.0;
    // barre de feux arrière
    if(q.z<-2.2 && abs(q.x)<0.85 && abs(q.y-0.8)<0.035) emi += vec3(1.0,0.02,0.02)*5.0;
    if(q.z<-2.2 && abs(abs(q.x)-0.75)<0.12 && abs(q.y-0.8)<0.06) emi += vec3(1.0,0.03,0.02)*8.0;
  } else if(mat<6.5){ // vitres
    alb = vec3(0.004); refl = 1.0; spec = 1.0;
  } else if(mat<7.5){ // pneus + jantes qui tournent
    vec3 q = p - vec3(uCarX,0.0,uCarZ);
    vec2 w = vec2(q.y-0.36, abs(q.z)-1.45);
    float r = length(w);
    float ang = atan(w.y, w.x) + uWheelAng*sign(q.z+1e-4)*0.0 + uWheelAng;
    alb = vec3(0.015);
    if(r<0.24 && abs(q.x)>0.9){
      float spokes = smoothstep(-0.15,0.35,cos(ang*5.0));
      alb = mix(vec3(0.006), vec3(0.16,0.165,0.17), spokes*smoothstep(0.24,0.21,r));
      alb = mix(alb, vec3(0.2), smoothstep(0.06,0.04,r));
      spec = 0.6*spokes;
    }
  } else if(mat<9.5){ // lampadaire
    alb = vec3(0.04);
    float k = floor(p.z/40.0);
    float hs = hash11(k*7.7+1.0);
    float on = hs<0.3 ? 0.0 : (hs<0.5 ? step(0.45, noise2(vec2(uTime*9.0,k))) : 1.0);
    if(p.y<7.42 && n.y<-0.5) emi += LAMP_COL*on*12.0;
  } else { // enseigne néon
    vec3 sl; signs(p, sl);
    float s = p.x>0.0?1.0:-1.0;
    float k = floor(p.z/CELL);
    alb = vec3(0.02);
    vec2 f = vec2(sl.x/0.7, sl.y);
    float frame = smoothstep(0.1,0.0,abs(max(abs(f.x),abs(f.y))-0.86));
    float bars = smoothstep(0.08,0.0,abs(fract(f.y*2.5)-0.5)-0.38)*step(abs(f.x),0.55)*step(abs(f.y),0.7);
    float pat = max(frame, bars*step(0.5,hash21(vec2(floor(f.y*2.5),k))));
    emi += neonColor(s,k)*neonFlicker(s,k)*pat*16.0;
  }
  // éclairage
  vec3 L = vec3(0.012,0.014,0.02)*(0.6+0.4*n.y)*occ;                // ciel nocturne
  vec3 fdir = normalize(vec3(-0.3,1.0,0.5));
  L += FLASH_COL*uFlash*(0.25+0.75*max(dot(n,fdir),0.0))*occ*occ*0.55;    // éclair
  L += localLights(p, n);
  vec3 col = alb*L + emi;
  // reflets spéculaires simulés pour les vitres d'immeubles
  if(spec>0.0 && refl<=0.0){
    vec3 r = reflect(rd, n);
    float fr = 0.04+0.96*pow(1.0-max(dot(-rd,n),0.0),5.0);
    col += envReflect(r)*fr*spec*0.8 + FLASH_COL*uFlash*fr*spec*0.6;
  }
  return col;
}

vec3 fogLight(vec3 p){
  vec3 L = vec3(0.016,0.019,0.026) + FLASH_COL*uFlash*0.2;
  L += localLights(p, vec3(0))*0.9;
  return L;
}

float fogDensity(vec3 p){
  float h = exp(-max(p.y,0.0)/14.0);
  float n = noise3(p*vec3(0.05,0.09,0.05) + vec3(uTime*0.35, -uTime*0.05, uTime*0.18));
  float n2 = noise3(p*0.17 + vec3(uTime*0.6,0.0,0.0));
  return uFog*(0.0035 + 0.022*h*(0.25+1.3*n*n+0.35*n2));
}

// brume volumétrique : renvoie transmittance, ajoute la lumière diffusée
vec3 applyFog(vec3 col, vec3 ro, vec3 rd, float tHit, float jitter){
  float tEnd = min(tHit, 220.0);
  const int N = 9;
  float T = 1.0; vec3 S = vec3(0);
  float prev = 0.0;
  for(int i=0;i<N;i++){
    float a = (float(i)+jitter)/float(N);
    float t = tEnd * a*a;
    float dt = t-prev; prev = t;
    vec3 p = ro+rd*t;
    float dens = fogDensity(p);
    float tr = exp(-dens*dt);
    S += T*(1.0-tr)*fogLight(p);
    T *= tr;
  }
  // tranche finale
  float dt = tEnd-prev;
  vec3 p = ro+rd*tEnd;
  float dens = fogDensity(p); float tr = exp(-dens*dt);
  S += T*(1.0-tr)*fogLight(p); T*=tr;
  if(tHit>220.0){ // au-delà : brume lointaine homogène
    float tr2 = exp(-uFog*0.0028*(min(tHit,600.0)-220.0));
    S += T*(1.0-tr2)*(vec3(0.016,0.019,0.026)+FLASH_COL*uFlash*0.9);
    T *= tr2;
  }
  return col*T + S;
}

// ---------------------------------------------------------------- rain
vec3 rain(vec3 ro, vec3 rd, vec3 cw, float tHit, vec2 frag){
  vec3 acc = vec3(0);
  float az = atan(rd.x, rd.z);
  float el = asin(clamp(rd.y,-1.0,1.0));
  float pix = 2.0*tan(uFov*0.5)/uRes.y;   // radians / pixel
  float tilt = sqrt(max(1.0-cw.y*cw.y, 0.05));
  vec3 right = normalize(vec3(cw.z, 0.0, -cw.x));
  float lat = dot(ro, right);
  const float DEP[6] = float[6](1.4, 2.6, 4.5, 8.0, 14.0, 26.0);
  for(int i=0;i<6;i++){
    float D = DEP[i];
    if(D>tHit) break;
    vec2 P = vec2(az*D - lat*0.0, el*D);
    P.x += P.y*0.12;                       // vent
    P.y += uTime*9.5 + float(i)*13.7;       // chute
    P.x += float(i)*7.3;
    vec2 cell = vec2(0.55, 1.6);
    vec2 g = P/cell; vec2 gi = floor(g); vec2 gf = fract(g);
    float h = hash21(gi+float(i)*17.0);
    if(h<0.25) continue;
    float cx = hash21(gi+3.3+float(i));
    float cy = hash21(gi+5.1);
    float len = 0.2*tilt/cell.y;
    float dy = (gf.y - cy);
    float w = max(0.003, pix*D*1.0);       // largeur monde ≥ 1 pixel
    float dx = abs(gf.x-cx)*cell.x;
    float cov = clamp(0.004/w, 0.0, 1.0);  // gouttes fines lointaines atténuées
    float streak = smoothstep(w, 0.0, dx)*smoothstep(len,len*0.6,abs(dy))*smoothstep(-len, -len*0.3, dy);
    streak *= step(abs(dy), len);
    if(streak<=0.0) continue;
    vec3 wp = ro + rd*D;
    vec3 lit = vec3(0.03,0.035,0.045) + FLASH_COL*uFlash*1.2 + localLights(wp, vec3(0))*1.4;
    acc += lit*streak*cov*(0.35+0.65*h)*(i<2?0.55:1.0);
  }
  return acc;
}

// ---------------------------------------------------------------- main
vec3 aces(vec3 x){ return clamp((x*(2.51*x+0.03))/(x*(2.43*x+0.59)+0.14),0.0,1.0); }

void main(){
  vec2 frag = gl_FragCoord.xy;
  vec2 uv = (frag - 0.5*uRes)/(0.5*uRes.y);
  vec3 ro = uCamPos;
  vec3 cw = normalize(uCamTgt-ro);
  vec3 cu = normalize(cross(cw, vec3(0,1,0)));
  vec3 cv = cross(cu, cw);
  float cr = cos(uRoll), sr = sin(uRoll);
  vec3 u2 = cu*cr + cv*sr, v2 = -cu*sr + cv*cr;
  vec3 rd = normalize(uv.x*u2 + uv.y*v2 + cw/tan(uFov*0.5));

  float jitter = fract(52.9829189*fract(dot(frag, vec2(0.06711056,0.00583715))) + uTime*7.13);

  float mat;
  float t = trace(ro, rd, 600.0, 160, mat);
  vec3 col;
  float tHit = 1e4;
  if(t<0.0){
    col = sky(rd);
  } else {
    tHit = t;
    vec3 p = ro+rd*t;
    vec3 n = calcNormal(p);
    float refl; vec3 rn;
    col = shade(p, n, rd, mat, true, refl, rn);
    if(refl>0.0){
      vec3 r = reflect(rd, rn);
      if(r.y<0.0 && mat<2.5) r.y = abs(r.y)*0.5;
      float cosT = max(dot(-rd, rn), 0.0);
      float F0 = mat<2.5 ? 0.03 : (mat<5.5 ? 0.06 : 0.08);
      float fr = F0 + (1.0-F0)*pow(1.0-cosT, 5.0);
      fr = mat<2.5 ? mix(fr, 0.55, 0.35*refl) : fr;   // eau sur bitume
      vec3 rc;
      float m2;
      vec3 ro2 = p + n*0.02;
      float t2 = trace(ro2, r, 300.0, 80, m2);
      if(t2<0.0) rc = sky(r);
      else {
        vec3 p2 = ro2 + r*t2;
        vec3 n2 = calcNormal(p2);
        float rf2; vec3 rn2;
        rc = shade(p2, n2, r, m2, false, rf2, rn2);
        if(rf2>0.0) rc += envReflect(reflect(r,n2))*0.1;
      }
      rc = applyFog(rc, ro2, r, t2<0.0?1e4:t2, jitter);
      col += rc*fr*refl;
    }
  }
  col = applyFog(col, ro, rd, tHit, jitter);
  col += rain(ro, rd, cw, tHit, frag);

  // étalonnage
  col *= uExposure*1.15;
  col = aces(col);
  float lum = dot(col, vec3(0.299,0.587,0.114));
  col = mix(col, col*vec3(0.86,1.0,1.12), 0.35*(1.0-smoothstep(0.0,0.5,lum)));
  col = pow(col, vec3(1.0/2.2));
  // vignettage
  vec2 q = frag/uRes;
  col *= 0.55 + 0.45*pow(16.0*q.x*q.y*(1.0-q.x)*(1.0-q.y), 0.22);
  fragColor = vec4(col, 1.0);
}
