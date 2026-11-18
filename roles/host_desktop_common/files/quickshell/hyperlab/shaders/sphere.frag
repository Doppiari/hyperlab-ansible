#version 440
// One glass network sphere for NetworkSphere.qml.
//
// A glass rim (fresnel and iridescence), engraved latitude and longitude, a
// specular highlight, a soft halo and the energy core. The item is a square
// about 2.4 sphere radii wide; qt_TexCoord0 is mapped to -1..1 over it and
// divided by radiusShare, so the sphere's own radius is 1.
//
// Every tint derives from `colour`, the network's palette colour. The only
// other constants are white light and the iridescence phase.
//
// `time` moves the core and the engraving only while the sphere is lit: a
// dark sphere is still, whatever time its parent passes.
//
// Rebuild sphere.frag.qsb with tools/build-shaders.sh after any change;
// verify.sh refuses a source that no longer matches shaders/SHADERS.sha256.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float lit;
    float character;
    float turn;
    float selected;
    float radiusShare;
    float pixelRadius;
    vec4 colour;
    vec2 light;
};

const float TAU = 6.2831853;
const vec3 IRIDESCENCE_PHASE = vec3(0.0, 0.33, 0.67);

float hash(vec3 p)
{
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float noise(vec3 x)
{
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash(i), hash(i + vec3(1.0, 0.0, 0.0)), f.x),
                   mix(hash(i + vec3(0.0, 1.0, 0.0)), hash(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
               mix(mix(hash(i + vec3(0.0, 0.0, 1.0)), hash(i + vec3(1.0, 0.0, 1.0)), f.x),
                   mix(hash(i + vec3(0.0, 1.0, 1.0)), hash(i + vec3(1.0, 1.0, 1.0)), f.x), f.y),
               f.z);
}

float fbm(vec3 p)
{
    float amplitude = 0.5;
    float sum = 0.0;
    for (int octave = 0; octave < 5; octave++) {
        sum += amplitude * noise(p);
        p = p * 2.02 + vec3(1.7, 9.2, 3.1);
        amplitude *= 0.5;
    }
    return sum;
}

vec3 turnY(vec3 p, float a)
{
    float c = cos(a);
    float s = sin(a);
    return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}

vec3 turnX(vec3 p, float a)
{
    float c = cos(a);
    float s = sin(a);
    return vec3(p.x, c * p.y - s * p.z, s * p.y + c * p.z);
}

// Engraved meridians every 60 degrees, parallels every 45 and the equator.
float engraving(vec3 n, float spin, float tilt)
{
    vec3 q = turnX(turnY(n, spin), tilt);
    float latitude = asin(clamp(q.y, -1.0, 1.0));
    float longitude = atan(q.z, q.x);
    float meridian = smoothstep(0.465, 0.493, abs(fract(longitude * 6.0 / TAU) - 0.5));
    float parallel = smoothstep(0.465, 0.493, abs(fract(latitude / 0.7854) - 0.5));
    float equator = smoothstep(0.03, 0.0, abs(q.y));
    return max(max(meridian, parallel) * 0.55, equator);
}

void main()
{
    vec2 d = (qt_TexCoord0 * 2.0 - 1.0) / radiusShare;
    float r2 = dot(d, d);
    float r = sqrt(r2);
    float edge = 1.0 / radiusShare;
    int kind = int(character + 0.5);
    vec3 C = colour.rgb;
    vec3 L = normalize(vec3(light, 0.7));

    // The only clock the sphere reads. A dark sphere stays at its first frame.
    float t = lit > 0.0 ? time : 0.0;

    float beat = kind == 0
        ? 0.82 + 0.18 * pow(0.5 + 0.5 * sin(t * 2.1), 8.0)
          + 0.1 * pow(0.5 + 0.5 * sin(t * 2.1 - 0.5), 14.0)
        : 1.0;
    float li = kind == 0 ? 0.6 * beat * lit : lit;

    vec3 acc = vec3(0.0);
    float alpha = 0.0;

    if (r < 1.0) {
        vec3 n = vec3(d.x, -d.y, sqrt(1.0 - r2));
        vec3 nb = vec3(d.x, -d.y, -n.z);
        float fresnel = pow(1.0 - n.z, 2.2);
        vec3 col = C * 0.045 + vec3(0.011);

        float spin = turn + t * (kind == 0 ? 0.05 : 0.12 + 0.1 * lit);
        float e1 = engraving(n, spin, 0.35) * (0.35 + 0.65 * n.z);
        float e2 = engraving(nb, spin, 0.35) * 0.35;

        float rc = kind == 0 ? 0.56 : 0.5;
        vec3 cc = vec3(0.0);
        float core = 0.0;
        if (r < rc) {
            vec2 dc = d / rc;
            float rr = dot(dc, dc);
            vec3 nc = vec3(dc.x, -dc.y, sqrt(max(0.0, 1.0 - rr)));
            float speed = kind == 4 ? 0.9 : kind == 2 ? 0.35 : kind == 3 ? 0.22 : kind == 0 ? 0.12 : 0.15;
            float scale = kind == 4 ? 3.6 : kind == 2 ? 2.6 : kind == 3 ? 2.0 : kind == 0 ? 2.2 : 1.7;
            vec3 w = turnY(nc, t * speed) * scale;
            float e = fbm(w + vec3(fbm(w * 1.3 + t * speed), 0.0, 0.0) * 1.4);
            if (kind == 3)
                e = 0.5 + 0.5 * sin(nc.y * 13.0 + e * 5.0 + t * 0.6);
            if (kind == 5) {
                float lattice = abs(sin(nc.x * 9.0) * sin(nc.y * 9.0 + 1.0));
                e = e * 0.5 + 0.25 * smoothstep(0.85, 1.0, lattice);
            }
            float hot = pow(nc.z, 3.0);
            vec3 cHot = kind == 4 ? mix(C, vec3(1.0), 0.8) : mix(C, vec3(1.0), 0.75);
            if (kind == 0) {
                // Silver: the host's own grey, darkened and lifted toward white.
                vec3 silver = mix(C * 0.47, mix(C, vec3(1.0), 0.6), e * e);
                cc = silver * (0.45 + 0.45 * e) + vec3(1.0) * hot * 0.22;
                cc *= beat * 0.9 * (0.16 + 0.84 * lit);
            } else {
                cc = C * (0.2 + 1.5 * e * e) + cHot * hot * (0.35 + 0.9 * e) * (kind == 4 ? 1.3 : 1.0);
                cc *= 0.16 + 0.84 * lit;
            }
            if (lit < 0.5)
                cc = mix(vec3(dot(cc, vec3(0.3, 0.59, 0.11))), cc, 0.7) * (0.55 + 0.8 * lit);
            core = smoothstep(rc, rc - 0.04, r);
        }
        col = mix(col, cc, core);
        col += C * exp(-max(r - rc, 0.0) * 5.5) * (0.14 + 0.42 * li);
        col += C * (e1 + e2) * (0.16 + 0.3 * li) + vec3(1.0) * e1 * 0.035;
        vec3 iridescence = 0.5 + 0.5 * cos(TAU * (fresnel * 1.6 + IRIDESCENCE_PHASE));
        col += C * fresnel * (0.45 + 0.55 * li) + iridescence * fresnel * 0.10
            + vec3(1.0) * fresnel * (0.05 + 0.08 * selected);
        float specular = max(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0);
        col += pow(specular, 70.0) * 1.15 + pow(specular, 6.0) * 0.06;

        float a = (0.86 + 0.14 * fresnel) * clamp((1.0 - r) * pixelRadius * 1.5, 0.0, 1.0);
        acc = col * a;
        alpha = a;
    }
    if (r >= 1.0 - 1.0 / max(pixelRadius, 1.0) && r < edge) {
        // The halo fades to nothing at the item's edge, so it is never cut.
        float reach = clamp((r - 1.0) / max(edge - 1.0, 0.001), 0.0, 1.0);
        float window = (1.0 - reach * reach) * (1.0 - reach * reach);
        float hl = kind == 0 ? 0.45 * beat * lit : lit;
        float g = exp(-max(r - 1.0, 0.0) * (hl > 0.4 ? 3.4 : 7.0)) * (hl > 0.4 ? 0.5 : 0.12) * window;
        float outside = 1.0 - alpha;
        acc += C * g * outside;
        alpha += g * 0.55 * outside;
    }
    fragColor = vec4(acc, clamp(alpha, 0.0, 1.0)) * qt_Opacity;
}
