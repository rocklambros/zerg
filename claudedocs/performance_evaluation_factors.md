# Performance Evaluation Factors (140 CLI-Evaluatable)

## 1. CPU and Compute (12 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 1 | Algorithm complexity | Big O analysis of core functions | lizard, radon | Constant-time required for crypto operations |
| 2 | Hot path identification | 80/20 rule: find the 20% causing 80% of load | perf, async-profiler | - |
| 3 | Branch prediction impact | Mispredicted branches cost 10-20 cycles each | perf stat | - |
| 4 | SIMD vectorization | Compiler auto-vectorization opportunities | gcc/clang -fopt-info-vec | - |
| 5 | Cache locality | L1 cache hit vs main memory: 1ns vs 100ns | perf stat, cachegrind | - |
| 6 | False sharing | Cache line contention between cores | perf c2c | - |
| 7 | Lock contention | Mutex wait time as percentage of execution | perf lock, mutrace | - |
| 8 | Context switching overhead | Thread/process switch cost | perf stat | - |
| 9 | Compiler optimization flags | -O0 vs -O3 can mean 10x difference | Semgrep (build files) | - |
| 10 | CPU limits in Kubernetes | Missing limits cause noisy neighbor problems | kube-linter, Kubescape | - |
| 11 | Cgroup configuration | v2 provides better resource isolation | Kubescape | - |
| 12 | NUMA awareness | Multi-socket servers need explicit memory placement | Semgrep, numactl | - |

---

## 2. Memory (9 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 13 | Allocation patterns | Object pooling vs heap allocation per request | heaptrack, Valgrind massif | Zero sensitive data before returning to pools |
| 14 | Stack vs heap allocation | Stack allocation is 100x faster than heap | Valgrind, AddressSanitizer | - |
| 15 | GC pressure | Frequent allocations trigger stop-the-world pauses | async-profiler, scalene | - |
| 16 | Working set size | Must fit in available RAM to avoid swapping | perf stat | - |
| 17 | Memory alignment | Misaligned access costs 2-10x on some architectures | pahole, Semgrep | - |
| 18 | Copy elimination | Zero-copy parsing avoids allocation overhead | Semgrep | - |
| 19 | Container memory limits | Missing limits risk OOM killer termination | kube-linter, Kubescape | - |
| 20 | Memory swappiness | Disable swap for containers to prevent latency spikes | Kubescape | - |
| 21 | Unbounded collection growth | Missing size limits cause memory exhaustion | Semgrep | Prevents memory exhaustion attacks |

---

## 3. Disk I/O (10 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 22 | Blocking vs async I/O | Blocking I/O ties up threads waiting for disk | Semgrep, strace | - |
| 23 | Access patterns | Sequential: 500MB/s, Random: 1MB/s on spinning disk | blktrace, strace | - |
| 24 | Buffer sizing | Match filesystem block size (typically 4KB) | strace | - |
| 25 | Write batching | Each fsync costs 5-20ms on HDD | Semgrep | Sync audit logs immediately |
| 26 | Memory-mapped files | Efficient for large file random access | Semgrep | Check file permissions before mmap |
| 27 | Container overlay filesystem | Each layer adds lookup overhead | dive, Hadolint | - |
| 28 | Copy-on-write penalty | First write to overlayed file copies entire file | dive | - |
| 29 | Volume mount types | Bind mounts faster than named volumes | kube-linter | - |
| 30 | tmpfs for ephemeral data | RAM-backed filesystem for temp files | kube-linter, Kubescape | Sensitive temp data stays in memory |
| 31 | Storage driver selection | overlay2 preferred over aufs/devicemapper | Trivy, Hadolint | - |

---

## 4. Network I/O (14 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 32 | Connection pooling | TCP handshake costs 1-3 RTTs | Semgrep | Re-authenticate pooled connections |
| 33 | Async I/O for high concurrency | Threads don't scale past thousands of connections | Semgrep | - |
| 34 | Request batching | Combine multiple operations into single round-trip | Semgrep | - |
| 35 | Serialization format overhead | JSON parsing 10-100x slower than Protocol Buffers | Semgrep, hyperfine | Validate all deserialized data |
| 36 | TCP tuning | Nagle's algorithm adds 40ms delay for small packets | Semgrep | - |
| 37 | Container network mode | Bridge adds NAT overhead vs host mode | kube-linter, Kubescape | Host mode reduces isolation |
| 38 | Network policy rule count | Large iptables rulesets add per-packet overhead | Kubescape | Default deny is worth the overhead |
| 39 | DNS resolution caching | Uncached DNS adds 10-100ms per lookup | Semgrep | Never hardcode IPs (breaks cert validation) |
| 40 | Service mesh sidecar overhead | Each hop adds 1-5ms latency | Kubescape | mTLS overhead is worth the security |
| 41 | CNI plugin selection | eBPF-based (Calico, Cilium) faster than iptables | Kubescape | - |
| 42 | Chatty interface detection | Multiple sequential calls vs single batch | Semgrep | - |
| 43 | Synchronous external calls | Blocking HTTP in request handlers kills throughput | Semgrep | - |
| 44 | Retry logic | Missing: single failure breaks chain. Infinite: amplifies outages | Semgrep | Never log credentials in retry attempts |
| 45 | Timeout configuration | Missing timeouts cause resource exhaustion | Semgrep | Prevents slowloris attacks |

---

## 5. Database (7 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 46 | N+1 query detection | 1 query + N child queries vs 1 query with JOIN | Semgrep, sqlfluff | - |
| 47 | Missing index indicators | WHERE/ORDER BY on unindexed columns | sqlfluff, pt-query-digest | - |
| 48 | Connection pool sizing | Too small: contention. Too large: memory waste | Semgrep | - |
| 49 | Prepared statement usage | Parse once, execute many. Also prevents SQL injection | Semgrep | Prevents SQL injection |
| 50 | Result set pagination | SELECT without LIMIT returns unbounded rows | Semgrep | Prevents enumeration attacks |
| 51 | ORM query inspection | ORMs generate suboptimal SQL without review | Semgrep | - |
| 52 | Eager loading patterns | select_related/prefetch_related vs lazy loading | Semgrep | - |

---

## 6. Caching (5 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 53 | Eviction policy configuration | LRU vs TTL vs size-based depends on access pattern | Semgrep | TTLs must align with session lifetimes |
| 54 | Cache stampede prevention | Lock or probabilistic refresh on expiration | Semgrep | - |
| 55 | Cache serialization cost | JSON serialization can negate cache benefit | hyperfine | Validate cached data on deserialization |
| 56 | Repeated parsing elimination | Parse once, cache structured result | Semgrep | - |
| 57 | Cache key construction | Missing user context enables cache poisoning | Semgrep | Include auth context in cache keys |

---

## 7. Concurrency Patterns (9 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 58 | Lock granularity | Global locks serialize everything | Semgrep, ThreadSanitizer | - |
| 59 | Read-write lock usage | Multiple readers, exclusive writers | Semgrep | - |
| 60 | Lock-free structure correctness | Incorrect atomics cause data corruption | Semgrep, Helgrind | Verify with formal methods before deploying |
| 61 | Thread pool sizing | CPU-bound: core count. I/O-bound: higher | Semgrep | Limit pool size to prevent thread exhaustion |
| 62 | Blocking calls in async context | Sync I/O in async function blocks event loop | Semgrep | - |
| 63 | Unnecessary async overhead | Async for CPU-bound work adds overhead | Semgrep | - |
| 64 | Sequential awaits in loops | await in loop executes serially | Semgrep | - |
| 65 | Over-synchronization | Locking more than necessary kills parallelism | Semgrep | Prove thread safety before removing locks |
| 66 | Thread-per-request assumption | Doesn't scale past thousands of concurrent requests | Semgrep | - |

---

## 8. Code-Level Patterns (7 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 67 | String concatenation in loops | O(n²) complexity. Use StringBuilder or join() | Semgrep | - |
| 68 | Regex compilation placement | Compile once outside loop, not per iteration | Semgrep | User-controlled regex enables ReDoS |
| 69 | Exception for control flow | Stack unwinding is expensive. Use conditionals | Semgrep | Never expose stack traces to users |
| 70 | Reflection in hot paths | 10-100x slower than direct calls | Semgrep | - |
| 71 | Lazy initialization overhead | Double-checked locking on every access | Semgrep | - |
| 72 | Collection type mismatch | List for membership test vs Set for O(1) lookup | Semgrep | - |
| 73 | String concatenation for queries | Performance and security disaster | Semgrep | Use parameterized queries |

---

## 9. Abstraction and Structure (5 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 74 | Over-abstraction | Interface with single implementation adds indirection | lizard, Semgrep | More code means more attack surface |
| 75 | Premature generalization | Generic code for single use case | Semgrep | - |
| 76 | Design pattern theater | Factory for simple instantiation | lizard, Semgrep | - |
| 77 | Wrapper explosion | Thin wrappers that add no value | Semgrep | - |
| 78 | DTO mapping chains | A→B→C→D when A→D would suffice | Semgrep | Mapping layers that filter sensitive fields add value |

---

## 10. Dependencies and Imports (4 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 79 | Dependency bloat | Unused dependencies increase attack surface and size | Trivy, deptry, depcheck | Fewer dependencies means fewer CVEs |
| 80 | Transitive dependency blindness | One import brings 200+ transitive deps | Trivy, pipdeptree, npm ls | Each transitive dep is a supply chain risk |
| 81 | Framework maximalism | Full framework for subset of features | Trivy, Semgrep | - |
| 82 | Reinventing standard library | Custom implementations of stdlib functions | Semgrep | Stdlib receives more security scrutiny |

---

## 11. Code Volume and Redundancy (5 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 83 | Excessive null handling | Optional/Maybe everywhere without proof of necessity | Semgrep | - |
| 84 | Copy-paste with variations | Same logic slightly modified in multiple places | jscpd, PMD CPD | Bug fixes miss copies |
| 85 | Comment noise | Comments that restate obvious code | Semgrep | - |
| 86 | Dead code | Unreachable code still gets compiled and deployed | vulture, ts-prune, deadcode | Dead code expands attack surface |
| 87 | Boilerplate explosion | Getters/setters/builders for simple data | Semgrep | Auto-generated toString leaks sensitive fields |

---

## 12. Type and Error Handling (4 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 88 | Exception class proliferation | Custom exception per error vs standard types | Semgrep, file count | - |
| 89 | Swallowed exceptions | catch (Exception e) { } hides failures | Semgrep | Log security-relevant exceptions |
| 90 | Sensitive data in logs | Passwords, tokens, PII in log statements | Semgrep | Never log credentials or PII |
| 91 | Redundant validation | Same validation at multiple layers | Semgrep | Validate untrusted input at boundary only |

---

## 13. Container Image and Build (6 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 92 | Image layer count | Each layer adds filesystem overhead | dive | - |
| 93 | Image size | Distroless: 50MB. Full OS: 2GB | dive, docker images | Smaller image means smaller attack surface |
| 94 | Build cache efficiency | Layer ordering affects rebuild time | Hadolint | - |
| 95 | Base image selection | Alpine/distroless vs full Ubuntu | Hadolint, Trivy | Distroless eliminates shell for attackers |
| 96 | Image vulnerability scanning | Known CVEs in base image and dependencies | Trivy | Block deployment on critical CVEs |
| 97 | Image signing and verification | Unsigned images can be tampered | cosign, Trivy | Verify signatures before deployment |

---

## 14. Container Runtime (4 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 98 | Container startup time | Cold start latency affects scaling | hyperfine | - |
| 99 | Unnecessary binaries in image | curl, wget, shell expand attack surface | dive, Trivy | Remove debugging tools from production |
| 100 | Security profile overhead | seccomp/AppArmor adds syscall filtering | kube-linter, Kubescape | Never disable for performance |
| 101 | Privileged mode usage | Privileged containers bypass all isolation | Kubescape | Never use privileged mode |

---

## 15. Orchestration Layer (5 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 102 | Resource request/limit gaps | Requests too low causes scheduling failures | kube-linter, Kubescape | - |
| 103 | Probe configuration | Aggressive probes add unnecessary load | kube-linter | - |
| 104 | Pod density optimization | Too few pods per node wastes resources | Kubescape | - |
| 105 | Network policy enforcement | Missing policies allow lateral movement | kube-linter, Kubescape | Default deny all, allow explicitly |
| 106 | Pod security standards | Privileged pods undermine isolation | Kubescape | Enforce restricted or baseline |

---

## 16. Logging and Observability (6 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 107 | Log driver configuration | json-file driver blocks on full buffer | Hadolint | - |
| 108 | Log volume in hot paths | Debug logging in request handlers adds latency | Semgrep | - |
| 109 | High-cardinality metrics | User ID as label explodes metric count | Semgrep | - |
| 110 | Trace context propagation | Missing headers break distributed tracing | Semgrep | - |
| 111 | Percentile metric usage | P99/P999 reveal tail latency | Semgrep | - |
| 112 | Audit log separation | Audit logs need tamper-evident storage | Semgrep, Kubescape | Separate audit logs from application logs |

---

## 17. Architecture (5 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 113 | Service call depth | Each hop adds latency and failure probability | Semgrep, service count | Each boundary is a trust boundary |
| 114 | Serialization boundary overhead | Every service boundary requires serialize/deserialize | Semgrep | Validate at every boundary |
| 115 | Microservice fragmentation | Too many services increases operational complexity | cloc, Dockerfile count | More services means more attack surface |
| 116 | Configuration sprawl | Config files scattered across services | Semgrep | Never store secrets in env vars |
| 117 | Inconsistent patterns across services | Mixed async models, multiple HTTP clients | Semgrep | Inconsistency breeds security gaps |

---

## 18. AI-Generated Code Detection (9 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 118 | Cyclomatic complexity spikes | AI generates correct but convoluted code | lizard | Complex code hides vulnerabilities |
| 119 | Allocation pattern analysis | AI often allocates unnecessarily | heaptrack, scalene | - |
| 120 | Dependency audit for bloat | AI adds dependencies for single functions | Trivy, deptry | Each dep is a supply chain risk |
| 121 | Binary size tracking | Unexplained size increases indicate bloat | size, bloaty | - |
| 122 | Startup time regression | New code slows initialization | hyperfine | - |
| 123 | Performance benchmark gates | CI must catch performance regressions | k6, hyperfine | - |
| 124 | Security pattern coverage | AI misses security patterns that scanners catch | Semgrep | AI optimizes for correctness not security |
| 125 | Excessive mocking in tests | AI over-mocks, hiding integration issues | Semgrep | Mocks hide security integration failures |
| 126 | Missing performance tests | AI rarely generates benchmarks | grep, Semgrep | - |

---

## 19. Security-Specific Patterns (14 factors)

| # | Factor | Description | CLI Tool | Security Note |
|---|--------|-------------|----------|---------------|
| 127 | SQL injection vectors | String concatenation in queries | Semgrep | Use parameterized queries |
| 128 | Command injection vectors | User input in shell commands | Semgrep | Use subprocess with array args |
| 129 | Path traversal vectors | User input in file paths | Semgrep | Validate and canonicalize paths |
| 130 | SSRF vectors | User input in URLs | Semgrep | Allowlist permitted hosts |
| 131 | Deserialization of untrusted data | Pickle, YAML load, Java serialization | Semgrep, Trivy | Use safe loaders only |
| 132 | Hardcoded secrets | API keys, passwords in source | Trivy, Semgrep | Use secret managers |
| 133 | Weak cryptography | MD5, SHA1, DES, small key sizes | Semgrep | Use current NIST recommendations |
| 134 | Insufficient randomness | Random vs SecureRandom | Semgrep | Use CSPRNG for security contexts |
| 135 | Missing input validation | Trust boundary without validation | Semgrep | Validate at system boundary |
| 136 | Missing output encoding | XSS via unencoded output | Semgrep | Context-appropriate encoding |
| 137 | Insecure TLS configuration | TLS 1.0/1.1, weak ciphers | Semgrep, Trivy | TLS 1.2+ with strong ciphers |
| 138 | Missing authentication checks | Endpoints without auth verification | Semgrep | Auth check on every protected endpoint |
| 139 | Missing authorization checks | Auth present but no permission check | Semgrep | Authorize every resource access |
| 140 | Exposed debug endpoints | /debug, /metrics without auth | Semgrep, Kubescape | Disable or protect in production |
