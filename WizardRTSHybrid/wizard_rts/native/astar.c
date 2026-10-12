/* A* kernel, a line-for-line port of workers._find_path_fast (same exploration order and tie-breaks: the heap key is
 * (f, insertion counter), a total order, so any correct heap pops the same sequence as Python's heapq).
 * Returns the path length (tiles after the start, goal last) and writes tile ids to `out` in order, or -1 when no path
 * is found within max_nodes. Arrays are bytes per tile: ok (enterable), blk (blocked), joined (may be NULL). */
#include <stdint.h>
#include <stdlib.h>

typedef struct { double f; int64_t c; int32_t n; } Item;

static void push(Item **h, int64_t *len, int64_t *cap, Item it) {
    if (*len == *cap) { *cap *= 2; *h = (Item *)realloc(*h, (size_t)*cap * sizeof(Item)); }
    int64_t i = (*len)++;
    Item *a = *h;
    while (i > 0) {
        int64_t p = (i - 1) >> 1;
        if (a[p].f < it.f || (a[p].f == it.f && a[p].c < it.c)) break;
        a[i] = a[p];
        i = p;
    }
    a[i] = it;
}

static Item pop(Item *a, int64_t *len) {
    Item top = a[0];
    Item last = a[--(*len)];
    int64_t n = *len, i = 0;
    for (;;) {
        int64_t l = 2 * i + 1;
        if (l >= n) break;
        int64_t r = l + 1, m = l;
        if (r < n && (a[r].f < a[l].f || (a[r].f == a[l].f && a[r].c < a[l].c))) m = r;
        if (last.f < a[m].f || (last.f == a[m].f && last.c < a[m].c)) break;
        a[i] = a[m];
        i = m;
    }
    if (n > 0) a[i] = last;
    return top;
}

int dmb_astar(int W, int H, const uint8_t *ok, const uint8_t *blk, const uint8_t *joined, int s, int g, int sx, int sy, int gx, int gy,
              int limit, int64_t max_nodes, int four, const int *ddx, const int *ddy, int ndirs, int *out) {
    int64_t cap = 1024, len = 0, counter = 0;
    Item *heap = (Item *)malloc((size_t)cap * sizeof(Item));
    int64_t total = (int64_t)W * H;
    double *cost = (double *)malloc((size_t)total * sizeof(double));
    int32_t *came = (int32_t *)malloc((size_t)total * sizeof(int32_t));
    for (int64_t i = 0; i < total; i++) { cost[i] = __builtin_inf(); came[i] = -1; }
    int xlo = sx - limit > 0 ? sx - limit : 0, xhi = sx + limit < W - 1 ? sx + limit : W - 1;
    int ylo = sy - limit > 0 ? sy - limit : 0, yhi = sy + limit < H - 1 ? sy + limit : H - 1;
    cost[s] = 0.0;
    Item first = {0.0, 0, s};
    push(&heap, &len, &cap, first);
    int result = -1;
    while (len > 0) {
        Item it = pop(heap, &len);
        int cur = it.n;
        if (counter > max_nodes) break;
        if (cur == g || (joined && joined[cur])) {
            int n = 0;
            for (int c = cur; c != s; c = came[c]) n++;
            int k = n;
            for (int c = cur; c != s; c = came[c]) out[--k] = c;
            result = n;
            break;
        }
        int cy = cur / W, cx = cur - cy * W;
        double base = cost[cur] + 1.0;
        for (int d = 0; d < ndirs; d++) {
            int dx = ddx[d], dy = ddy[d];
            int nx = cx + dx, ny = cy + dy;
            if (nx < xlo || nx > xhi || ny < ylo || ny > yhi) continue;
            int n = cur + dy * W + dx;
            if (!ok[n] || (n != g && blk[n])) continue;
            if (dx && dy && (blk[cur + dx] || blk[cur + dy * W])) continue;
            if (base < cost[n]) {
                cost[n] = base;
                came[n] = cur;
                counter++;
                int ax = gx - nx, ay = gy - ny;
                if (ax < 0) ax = -ax;
                if (ay < 0) ay = -ay;
                double h = four ? (double)(ax + ay) : (double)(ax > ay ? ax : ay);
                Item ni = {base + h, counter, n};
                push(&heap, &len, &cap, ni);
            }
        }
    }
    free(heap); free(cost); free(came);
    return result;
}
