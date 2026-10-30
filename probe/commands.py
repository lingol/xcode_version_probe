#!/usr/bin/env python3
"""Pinned upstream regression probes. PASS reports observed behavior, never ancestry."""
import hashlib,json,os,pathlib,re,subprocess,sys
def arc_details(text):
 def body(name):
  m=re.search(r'define\b[^\n]*@'+re.escape(name)+r'\([^\n]*\)[^{]*\{(.*?)^\}',text,re.M|re.S)
  if not m:raise ValueError('Missing output function '+name)
  return m.group(1)
 mono=body('retain_motion_monotonic_store');release=body('dont_move_retain_past_release_store');unowned=body('dont_remove_check_unowned_across_release_store')
 control='@swift_retain' not in mono and '@swift_release' not in mono and 'store atomic' in mono
 barrier=re.search(r'@swift_retain\(.*?store atomic[^\n]*\brelease\b.*?@swift_release\(',release,re.S) is not None
 count=len(re.findall(r'call\b[^\n]*@swift_checkUnowned\(',unowned))
 return dict(monotonic_control_passed=control,release_retain_store_release_order_preserved=barrier,unowned_check_count=count,two_unowned_checks_preserved=count==2)

def arc_checks(text):
 d=arc_details(text)
 return d['monotonic_control_passed'],d['release_retain_store_release_order_preserved'] and d['two_unowned_checks_preserved']

def sil_checks(text):
 def body(name):
  m=re.search(r'^sil\b[^\n]*@'+name+r'\b[^\n]*\{(.*?)^\}',text,re.M|re.S)
  if not m:raise ValueError('Missing output function '+name)
  return m.group(1)
 b=body('address_stored_as_pointer');c=body('probe_plain_store')
 control=' load ' not in c and re.search(r'return %0\b',c) is not None
 regression=re.search(r'\bapply\b.*?(%\w+) = load \[trivial\].*?return \1\b',b,re.S) is not None
 return control,regression

def checker_self_test():
 ir='''
define void @retain_motion_monotonic_store(ptr %A, ptr %L) {
 store atomic i64 0, ptr %L monotonic, align 8
 ret void
}
define void @dont_move_retain_past_release_store(ptr %A, ptr %L) {
 call ptr @swift_retain(ptr %A)
 store atomic i64 0, ptr %L release, align 8
 call void @swift_release(ptr %A)
 ret void
}
define void @dont_remove_check_unowned_across_release_store(ptr %A, ptr %L) {
 call void @swift_checkUnowned(ptr %A)
 store atomic i64 0, ptr %L release, align 8
 call void @swift_checkUnowned(ptr %A)
 ret void
}
'''
 assert arc_checks(ir)==(True,True)
 assert arc_checks(ir.replace(' call ptr @swift_retain(ptr %A)\n',''))==(True,False)
 assert arc_checks(ir.replace(' call void @swift_checkUnowned(ptr %A)\n','',1))==(True,False)
 assert arc_checks(ir.replace(' store atomic i64 0, ptr %L monotonic',' call ptr @swift_retain(ptr %A)\n store atomic i64 0, ptr %L monotonic'))==(False,True)
 assert arc_checks(ir.replace('store atomic i64 0, ptr %L release','store atomic i64 0, ptr %L monotonic'))==(True,False)
 sil='''
sil [ossa] @address_stored_as_pointer : $@convention(thin) (Int) -> Int {
bb0(%0 : $Int):
 %7 = apply %6(%3) : $@convention(thin) (@inout Builtin.RawPointer) -> ()
 %8 = load [trivial] %1 : $*Int
 return %8 : $Int
}
sil [ossa] @probe_plain_store : $@convention(thin) (Int) -> Int {
bb0(%0 : $Int):
 return %0 : $Int
}
'''
 assert sil_checks(sil)==(True,True)
 assert sil_checks(sil.replace('return %8','return %0'))==(True,False)
 assert sil_checks(sil.replace('%8 = load [trivial] %1 : $*Int','%8 = integer_literal $Builtin.Int64, 0'))==(True,False)
 assert sil_checks(sil.replace(' return %0 : $Int',' %2 = load [trivial] %1 : $*Int\n return %2 : $Int'))==(False,True)
 for fn in (arc_checks,sil_checks):
  try:fn('')
  except ValueError:pass
  else:raise AssertionError('Missing function accepted')
 print('Checker self-tests: PASS (positive, negative and missing-function cases)')

checker_self_test()
if '--self-test' in sys.argv:sys.exit(0)

out=pathlib.Path('probe-results');out.mkdir(exist_ok=True)
results=[]
def run(name,args):
 p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
 (out/(name+'.stdout')).write_text(p.stdout);(out/(name+'.stderr')).write_text(p.stderr)
 print('COMMAND',name,json.dumps(args),'EXIT',p.returncode,flush=True)
 if p.stderr:print(p.stderr,flush=True)
 return p

def record(name,status,detail):
 results.append(dict(probe=name,status=status,detail=detail));print(name,status,detail,flush=True)

def fetch(name,sha,path):
 # The pinned files are repository inputs: no network or floating source refs.
 source_dir=pathlib.Path(__file__).resolve().parent/'probes'
 manifest=json.loads((source_dir/'SOURCES.json').read_text())
 meta=manifest[name]
 expected_url=f'https://raw.githubusercontent.com/swiftlang/swift/{sha}/{path}'
 if meta['url']!=expected_url:raise ValueError('Source URL pin mismatch: '+name)
 data=(source_dir/name).read_bytes()
 actual=hashlib.sha256(data).hexdigest()
 if actual!=meta['sha256']:raise ValueError('Source SHA256 mismatch: '+name)
 dest=out/name;dest.write_bytes(data)
 (out/(name+'.source.json')).write_text(json.dumps(meta,indent=2)+'\n')
 return dest

def tool(name):
 p=run('locate-'+name,['xcrun','--toolchain','XcodeDefault','--find',name]);return p.stdout.strip() if p.returncode==0 else None

swiftc=tool('swiftc');frontend=tool('swift-frontend');silopt=tool('sil-opt');arcopt=tool('swift-llvm-opt')
sdk_result=run('macos-sdk',['xcrun','--sdk','macosx','--show-sdk-path'])
if sdk_result.returncode or not pathlib.Path(sdk_result.stdout.strip()).is_dir():
 record('sdk','ERROR','Selected macOS SDK unavailable; no compiler regressions executed.')
 (out/'summary.json').write_text(json.dumps(results,indent=2));sys.exit(1)
sdk=sdk_result.stdout.strip()
print('Explicit macOS SDK:',sdk,flush=True)
# PR 92708: exact new source test, compiler verifier catches missing dealloc_stack.
try:
 weak=fetch('weak_capture_osize_stack_leak.swift','0671aa70aa028f83a7336e3c4820c3489ea2ff69','test/SILOptimizer/weak_capture_osize_stack_leak.swift')
 for label,flags in [('control-Onone',['-Onone']),('Osize',['-Osize']),('Osize-CMO',['-Osize','-cross-module-optimization'])]:
  p=run('92708-'+label,[swiftc,'-sdk',sdk,*flags,'-Xfrontend','-sil-verify-all','-emit-sil',str(weak),'-o',str(out/('92708-'+label+'.sil'))])
  record('92708-'+label,'PASS' if p.returncode==0 else 'ERROR',dict(compiled_with_sil_verification=p.returncode==0,compiler_exit_code=p.returncode,scope='Exact upstream source only; no source ancestry inference. Errors require log review.'))
except Exception as e:record('92708','ERROR',str(e))
# PR 92755: exact upstream ARC pass and added test functions. Frontend multicall
# invocation is itself an upstream RUN line, but may be omitted in retail builds.
try:
 ir=fetch('basic.ll','a15dfed774de584fafcaf656e35566e1daac2eeb','test/LLVMPasses/basic.ll')
 command=[arcopt] if arcopt else [frontend,'-swift-llvm-opt'] if frontend else None
 if not command:record('92755','SKIP','No shipped Swift LLVM optimizer entry point.')
 else:
  help_result=run('92755-tool-help',command+['--help'])
  if help_result.returncode!=0:record('92755','SKIP','Swift LLVM optimizer entry point unavailable; see help log.')
  else:
   p=run('92755-arc',command+['-passes=swift-llvm-arc-optimize',str(ir)])
   if p.returncode:record('92755','ERROR','Optimizer invocation failed; do not classify as patch missing.')
   else:
    control,check=arc_checks(p.stdout)
    record('92755','PASS' if control and check else 'FAIL' if control else 'INCONCLUSIVE',dict(**arc_details(p.stdout),scope='Shipped pass behavior, not source ancestry.'))
except Exception as e:record('92755','ERROR',str(e))
# PR 92632: original SIL regression with a plain-store forwarding control.
try:
 sil=fetch('redundant_load_elim_ossa.sil','d47335d8962d795627f87bd2275d019a862c3902','test/SILOptimizer/redundant_load_elim_ossa.sil')
 sil_command=[silopt] if silopt else [frontend,'-sil-opt'] if frontend else None
 sil_help=run('92632-tool-help',sil_command+['--help']) if sil_command else None
 if not sil_help or sil_help.returncode!=0:record('92632','SKIP','No available shipped SIL optimizer entry point; generic source smoke tests would not prove this precise alias-analysis fix.')
 else:
  control='''\nsil [ossa] @probe_plain_store : $@convention(thin) (Int) -> Int {\nbb0(%0 : $Int):\n  %1 = alloc_stack $Int\n  store %0 to [trivial] %1\n  %2 = load [trivial] %1\n  dealloc_stack %1\n  return %2\n}\n'''
  test=out/'92632-with-control.sil';test.write_text(sil.read_text()+control)
  p=run('92632-sil',sil_command+['-sdk',sdk,'-sil-print-types','-enable-sil-verify-all',str(test),'-redundant-load-elimination'])
  if p.returncode:record('92632','ERROR','SIL test cannot run with this shipped tool; inspect parser/pass logs.')
  else:
   control_ok,m=sil_checks(p.stdout)
   record('92632','PASS' if control_ok and m else 'FAIL' if control_ok else 'INCONCLUSIVE',dict(plain_store_control_forwarded=control_ok,post_call_load_return_preserved=m,scope='Shipped pass behavior, not source ancestry.'))
except Exception as e:record('92632','ERROR',str(e))
(out/'summary.json').write_text(json.dumps(results,indent=2))
# SKIP is intentional and never represented as a passing regression.
print(json.dumps(results,indent=2))

sys.exit(1 if any(r["status"] in {"FAIL", "ERROR", "INCONCLUSIVE"} for r in results) else 0)
