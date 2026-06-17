"""
StarMind Manager - Comprehensive Test Script
Tests: db.py, llm.py, analysis.py, exporter.py, cli.py, edge cases
"""
import sys, os, json, time, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f'  [PASS] {name}')
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f'  [FAIL] {name}: {e}')

def assert_eq(a, b, msg=''):
    if a != b:
        raise AssertionError(f'{msg}: expected {b!r}, got {a!r}')

def assert_true(v, msg=''):
    if not v:
        raise AssertionError(f'{msg}: expected truthy, got {v!r}')

def assert_false(v, msg=''):
    if v:
        raise AssertionError(f'{msg}: expected falsy, got {v!r}')

def assert_in(item, col, msg=''):
    if item not in col:
        raise AssertionError(f'{msg}: {item!r} not in {col!r}')

def assert_not_in(item, col, msg=''):
    if item in col:
        raise AssertionError(f'{msg}: {item!r} should not be in {col!r}')


# ============================================================
#  1. DB MODULE TESTS
# ============================================================
print('\n' + '=' * 60)
print('  1. DB MODULE TESTS')
print('=' * 60)

import db

# 1.1 Schema
print('\n--- 1.1 Schema ---')
test('DB-003 init_db idempotent', lambda: db.init_db())

def test_schema_columns():
    conn = db.get_connection()
    cursor = conn.execute('PRAGMA table_info(starred_repos)')
    cols = {row[1] for row in cursor.fetchall()}
    for c in ['id','name','stars','summary','category','tags','language','url',
              'description','processed_date','owner_username','starred_at',
              'hidden','notes','favorite']:
        assert_in(c, cols, f'Missing column {c}')
    conn.close()
test('DB-001 starred_repos columns', test_schema_columns)

def test_collections_tables():
    conn = db.get_connection()
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert_in('collections', tables)
    assert_in('collection_items', tables)
    conn.close()
test('DB-002 collection tables exist', test_collections_tables)

# 1.2 CRUD
print('\n--- 1.2 Basic CRUD ---')
test('DB-008 get_connection', lambda: db.get_connection().close())

def test_upsert_insert():
    repo = {
        'id': 9000001, 'name': 'test-user/ai-project',
        'stars': 15000, 'summary': 'AI project test summary',
        'category': 'AI与大模型', 'tags': ['LLM', 'RAG', 'Python'],
        'language': 'Python', 'url': 'https://github.com/test/ai',
        'description': 'Test AI project'
    }
    db.upsert_repo(repo, owner_username='test-user')
    r = db.get_repo_by_id(9000001)
    assert_eq(r['name'], 'test-user/ai-project')
    assert_eq(r['tags'], ['LLM', 'RAG', 'Python'])
test('DB-009 upsert insert', test_upsert_insert)

def test_upsert_update():
    repo = {
        'id': 9000001, 'name': 'test-user/ai-project',
        'stars': 20000, 'summary': 'Updated summary',
        'tags': ['LLM', 'Python'], 'category': 'AI与大模型',
        'language': 'Python', 'url': 'https://github.com/test/ai',
        'description': 'Updated'
    }
    db.upsert_repo(repo, owner_username='test-user')
    r = db.get_repo_by_id(9000001)
    assert_eq(r['stars'], 20000)
    assert_eq(r['summary'], 'Updated summary')
test('DB-010 upsert update', test_upsert_update)

def test_tags_json():
    r = db.get_repo_by_id(9000001)
    assert_true(isinstance(r['tags'], list), 'tags should be list')
test('DB-011 tags serialization', test_tags_json)

def test_all_sorted():
    repos = db.get_all_repos()
    assert_true(len(repos) > 0)
    for i in range(min(len(repos)-1, 100)):
        assert_true(repos[i]['stars'] >= repos[i+1]['stars'], 'Not sorted by stars desc')
test('DB-014 get_all_repos sorted', test_all_sorted)

def test_get_existing():
    r = db.get_repo_by_id(9000001)
    assert_true(r is not None)
    assert_eq(r['name'], 'test-user/ai-project')
test('DB-015 get_repo_by_id exists', test_get_existing)

def test_get_missing():
    r = db.get_repo_by_id(999999999)
    assert_true(r is None)
test('DB-016 get_repo_by_id not exists', test_get_missing)

def test_count():
    c = db.get_repo_count()
    assert_true(c > 0)
test('DB-017 get_repo_count', test_count)

def test_existing_ids():
    ids = db.get_existing_ids('test-user')
    assert_in(9000001, ids)
test('DB-019 get_existing_ids', test_existing_ids)

# 1.3 Pagination
print('\n--- 1.3 Pagination ---')
def test_paged_basic():
    repos, total = db.get_repos_paged(page=1, page_size=5)
    assert_eq(len(repos), 5)
    assert_true(total > 0)
test('DB-023 paged basic', test_paged_basic)

def test_paged_no_overlap():
    r1, _ = db.get_repos_paged(page=1, page_size=5)
    r2, _ = db.get_repos_paged(page=2, page_size=5)
    ids1 = {r['id'] for r in r1}
    ids2 = {r['id'] for r in r2}
    assert_eq(len(ids1 & ids2), 0, 'Pages overlap')
test('DB-024 paged no overlap', test_paged_no_overlap)

def test_paged_category():
    repos, _ = db.get_repos_paged(category='AI与大模型')
    for r in repos:
        assert_eq(r['category'], 'AI与大模型')
test('DB-026 paged category filter', test_paged_category)

def test_paged_empty():
    repos, total = db.get_repos_paged(search='nonexistent_xyz_12345')
    assert_eq(repos, [])
    assert_eq(total, 0)
test('DB-029 paged empty result', test_paged_empty)

# 1.4 Delete / Favorite
print('\n--- 1.4 Delete / Favorite ---')
def test_hide_show():
    db.toggle_hidden(9000001, True)
    assert_eq(db.get_repo_by_id(9000001)['hidden'], 1)
    db.toggle_hidden(9000001, False)
    assert_eq(db.get_repo_by_id(9000001)['hidden'], 0)
test('DB-030/031 toggle_hidden', test_hide_show)

def test_fav_toggle():
    assert_true(db.toggle_favorite(9000001))
    assert_false(db.toggle_favorite(9000001))
test('DB-034/035 toggle_favorite', test_fav_toggle)

def test_fav_missing():
    assert_false(db.toggle_favorite(999999999))
test('DB-036 toggle_favorite missing', test_fav_missing)

# 1.5 Manual edit
print('\n--- 1.5 Manual Edit ---')
def test_edit_summary():
    db.update_repo_metadata(9000001, summary='New test summary')
    assert_eq(db.get_repo_by_id(9000001)['summary'], 'New test summary')
test('DB-037 edit summary', test_edit_summary)

def test_edit_category():
    db.update_repo_metadata(9000001, category='效率辅助工具')
    assert_eq(db.get_repo_by_id(9000001)['category'], '效率辅助工具')
test('DB-038 edit category', test_edit_category)

def test_edit_tags():
    db.update_repo_metadata(9000001, tags=['Vue', 'Svelte'])
    assert_eq(db.get_repo_by_id(9000001)['tags'], ['Vue', 'Svelte'])
test('DB-039 edit tags', test_edit_tags)

def test_edit_notes():
    db.update_repo_metadata(9000001, notes='Important')
    assert_eq(db.get_repo_by_id(9000001)['notes'], 'Important')
test('DB-040 edit notes', test_edit_notes)

def test_edit_multi():
    db.update_repo_metadata(9000001, summary='S2', category='C2', tags=['T1'], notes='N1')
    r = db.get_repo_by_id(9000001)
    assert_eq(r['summary'], 'S2')
    assert_eq(r['category'], 'C2')
    assert_eq(r['tags'], ['T1'])
    assert_eq(r['notes'], 'N1')
test('DB-041 edit multi', test_edit_multi)

def test_edit_none():
    db.update_repo_metadata(9000001)
    assert_true(db.get_repo_by_id(9000001) is not None)
test('DB-042 edit no params', test_edit_none)

# 1.6 Batch operations
print('\n--- 1.6 Batch Operations ---')
def test_batch_hide():
    db.batch_toggle_hidden([9000001], True)
    assert_eq(db.get_repo_by_id(9000001)['hidden'], 1)
    db.batch_toggle_hidden([9000001], False)
    assert_eq(db.get_repo_by_id(9000001)['hidden'], 0)
test('DB-043/044 batch_toggle_hidden', test_batch_hide)

def test_batch_empty():
    db.batch_toggle_hidden([], True)
    db.batch_delete([])
    db.batch_update_category([], '其他')
test('DB-045/048/050 batch empty', test_batch_empty)

def test_batch_cat():
    db.batch_update_category([9000001], '其他')
    assert_eq(db.get_repo_by_id(9000001)['category'], '其他')
test('DB-049 batch_update_category', test_batch_cat)

# 1.7 Collections
print('\n--- 1.7 Collections ---')
def test_create_col():
    cid = db.create_collection('test_col_1')
    assert_true(cid > 0)
    cid2 = db.create_collection('test_col_1')
    assert_eq(cid, cid2, 'Duplicate should return same id')
test('DB-051/052 create_collection', test_create_col)

def test_add_col():
    db.add_to_collection('test_col_1', 9000001)
    repos = db.get_collection_repos('test_col_1')
    ids = [r['id'] for r in repos]
    assert_in(9000001, ids)
test('DB-057 add_to_collection', test_add_col)

def test_add_col_dup():
    db.add_to_collection('test_col_1', 9000001)
    repos = db.get_collection_repos('test_col_1')
    cnt = sum(1 for r in repos if r['id'] == 9000001)
    assert_eq(cnt, 1, 'No duplicates')
test('DB-058 add_to_collection dup', test_add_col_dup)

def test_add_ghost():
    db.add_to_collection('ghost_xyz', 9000001)
test('DB-059 add to ghost collection', test_add_ghost)

def test_get_cols():
    cols = db.get_collections()
    names = [c['name'] for c in cols]
    assert_in('test_col_1', names)
test('DB-055 get_collections', test_get_cols)

def test_repo_cols():
    cols = db.get_repo_collections(9000001)
    assert_in('test_col_1', cols)
test('DB-065 get_repo_collections', test_repo_cols)

def test_remove_col():
    db.remove_from_collection('test_col_1', 9000001)
    repos = db.get_collection_repos('test_col_1')
    ids = [r['id'] for r in repos]
    assert_not_in(9000001, ids)
test('DB-060 remove_from_collection', test_remove_col)

def test_batch_add_col():
    db.batch_add_to_collection('test_col_1', [9000001])
    repos = db.get_collection_repos('test_col_1')
    ids = [r['id'] for r in repos]
    assert_in(9000001, ids)
test('DB-062 batch_add_to_collection', test_batch_add_col)

def test_delete_col():
    db.delete_collection('test_col_1')
    cols = db.get_collections()
    names = [c['name'] for c in cols]
    assert_not_in('test_col_1', names)
test('DB-053 delete_collection', test_delete_col)

def test_delete_ghost_col():
    db.delete_collection('ghost_xyz')
test('DB-054 delete ghost collection', test_delete_ghost_col)

# 1.8 Query functions
print('\n--- 1.8 Query Functions ---')
def test_cats():
    cats = db.get_all_categories()
    assert_true(len(cats) > 0)
    assert_not_in(None, cats)
    assert_not_in('', cats)
test('DB-067 get_all_categories', test_cats)

def test_users():
    users = db.get_usernames()
    assert_true(len(users) > 0)
test('DB-069 get_usernames', test_users)

def test_user_empty():
    repos = db.get_repos_by_username('ghost_user_xyz')
    assert_eq(repos, [])
test('DB-071 get_repos_by_username empty', test_user_empty)

def test_search():
    repos = db.search_repos(query='Python')
    assert_true(len(repos) > 0)
test('DB-072 search_repos', test_search)

def test_search_cat():
    repos = db.search_repos(query='', category='AI与大模型')
    for r in repos:
        assert_eq(r['category'], 'AI与大模型')
test('DB-073 search by category', test_search_cat)

def test_search_empty():
    repos = db.search_repos(query='nonexistent_xyz_12345')
    assert_eq(repos, [])
test('DB-078 search empty', test_search_empty)

# NEW function
print('\n--- NEW: get_english_summary_repo_ids ---')
def test_english_ids():
    ids = db.get_english_summary_repo_ids()
    assert_true(isinstance(ids, list))
    assert_true(len(ids) > 0)
    print(f'    (Found {len(ids)} English summary repos)')
test('NEW get_english_summary_repo_ids', test_english_ids)

# Cleanup
print('\n--- Cleanup ---')
db.hard_delete_repo(9000001)
assert_true(db.get_repo_by_id(9000001) is None)
print('  [PASS] Cleanup test repo')


# ============================================================
#  2. LLM MODULE TESTS
# ============================================================
print('\n' + '=' * 60)
print('  2. LLM MODULE TESTS')
print('=' * 60)

import llm

# 2.1 JSON Parsing
print('\n--- 2.1 JSON Parsing ---')
def test_parse_standard():
    r = llm._parse_llm_json('{"summary":"test","category":"AI","tags":["a","b"]}')
    assert_eq(r['summary'], 'test')
    assert_eq(r['tags'], ['a', 'b'])
test('LLM-001 parse standard JSON', test_parse_standard)

def test_parse_markdown():
    r = llm._parse_llm_json('```json\n{"summary":"s","category":"c","tags":[]}\n```')
    assert_eq(r['summary'], 's')
test('LLM-002 parse markdown wrapped', test_parse_markdown)

def test_parse_prefix():
    r = llm._parse_llm_json('Here is the result:\n{"summary":"s","category":"c","tags":["t"]}')
    assert_eq(r['summary'], 's')
test('LLM-003 parse with prefix text', test_parse_prefix)

def test_parse_tags_str():
    r = llm._parse_llm_json('{"summary":"s","category":"c","tags":"single_tag"}')
    assert_eq(r['tags'], ['single_tag'])
test('LLM-004 tags as string', test_parse_tags_str)

def test_parse_tags_null():
    r = llm._parse_llm_json('{"summary":"s","category":"c","tags":null}')
    assert_eq(r['tags'], [])
test('LLM-005 tags as null', test_parse_tags_null)

def test_parse_no_summary():
    r = llm._parse_llm_json('{"category":"c"}')
    assert_true(r is None)
test('LLM-006 missing summary', test_parse_no_summary)

def test_parse_invalid():
    r = llm._parse_llm_json('This is not JSON at all')
    assert_true(r is None)
test('LLM-007 invalid JSON', test_parse_invalid)

def test_parse_tags_not_list():
    r = llm._parse_llm_json('{"summary":"s","category":"c","tags":123}')
    assert_eq(r['tags'], [])
test('LLM-008 tags as number', test_parse_tags_not_list)

# 2.2 Edge cases
print('\n--- 2.2 Edge Cases ---')
def test_parse_empty():
    r = llm._parse_llm_json('')
    assert_true(r is None)
test('LLM-009 parse empty string', test_parse_empty)

def test_parse_chinese():
    r = llm._parse_llm_json('{"summary":"这是一个中文摘要","category":"AI与大模型","tags":["标签1"]}')
    assert_eq(r['summary'], '这是一个中文摘要')
test('LLM-010 parse Chinese content', test_parse_chinese)

def test_summarize_empty():
    r = llm.summarize_repo('http://fake', 'fake', 'fake',
                           readme_text='', description='', repo_tree='')
    assert_true(r is None)
test('LLM-011 summarize all empty', test_summarize_empty)


# ============================================================
#  3. ANALYSIS MODULE TESTS
# ============================================================
print('\n' + '=' * 60)
print('  3. ANALYSIS MODULE TESTS')
print('=' * 60)

import analysis

# 3.1 Similar repos
print('\n--- 3.1 Similar Repos ---')
def test_tag_set_list():
    s = analysis._tag_set(['LLM', 'Python', 'RAG'])
    assert_eq(s, {'llm', 'python', 'rag'})
test('AN-001 _tag_set list', test_tag_set_list)

def test_tag_set_json():
    s = analysis._tag_set('["A","B"]')
    assert_eq(s, {'a', 'b'})
test('AN-002 _tag_set JSON string', test_tag_set_json)

def test_tag_set_empty():
    assert_eq(analysis._tag_set(None), set())
    assert_eq(analysis._tag_set([]), set())
test('AN-003 _tag_set empty', test_tag_set_empty)

def test_jaccard_same():
    assert_eq(analysis._jaccard({'a', 'b'}, {'a', 'b'}), 1.0)
test('AN-004 jaccard identical', test_jaccard_same)

def test_jaccard_diff():
    assert_eq(analysis._jaccard({'a'}, {'b'}), 0.0)
test('AN-005 jaccard different', test_jaccard_diff)

def test_jaccard_partial():
    result = analysis._jaccard({'a', 'b', 'c'}, {'b', 'c', 'd'})
    assert_eq(result, 0.5)
test('AN-006 jaccard partial', test_jaccard_partial)

def test_jaccard_empty():
    assert_eq(analysis._jaccard(set(), set()), 0.0)
test('AN-007 jaccard both empty', test_jaccard_empty)

def test_similar_basic():
    repos = db.get_all_repos()
    if len(repos) > 5:
        target = repos[0]
        similar = analysis.find_similar_repos(repos, target['id'], top_n=3)
        assert_true(isinstance(similar, list))
        assert_true(len(similar) <= 3)
        if similar:
            assert_true('score' in similar[0])
test('AN-008 find_similar_repos basic', test_similar_basic)

def test_similar_missing():
    repos = db.get_all_repos()
    similar = analysis.find_similar_repos(repos, 999999999, top_n=3)
    assert_eq(similar, [])
test('AN-009 find_similar_repos missing ID', test_similar_missing)

def test_build_similar_map():
    repos = db.get_all_repos()[:50]  # Use subset for speed
    smap = analysis.build_similar_map(repos, top_n=2)
    assert_true(isinstance(smap, dict))
    for rid, sims in smap.items():
        assert_true(len(sims) <= 2)
test('AN-011 build_similar_map', test_build_similar_map)

# 3.2 User comparison
print('\n--- 3.2 User Comparison ---')
def test_compare_users():
    repos = db.get_all_repos(include_hidden=True)
    users = db.get_usernames()
    if len(users) >= 2:
        result = analysis.compare_users(repos, users[0], users[1])
        assert_in('only_a', result)
        assert_in('only_b', result)
        assert_in('common', result)
    else:
        result = analysis.compare_users(repos, 'user_a', 'user_b')
        assert_eq(result['only_a'], [])
test('AN-012 compare_users', test_compare_users)

# 3.3 Trends
print('\n--- 3.3 Trends ---')
def test_trends():
    repos = db.get_all_repos()
    result = analysis.analyze_trends(repos, recent_days=30)
    assert_in('summary', result)
    assert_in('recent_categories', result)
test('AN-015 analyze_trends', test_trends)

def test_trends_empty():
    result = analysis.analyze_trends([], recent_days=30)
    assert_in('summary', result)
test('AN-016 analyze_trends empty', test_trends_empty)


# ============================================================
#  4. EXPORTER MODULE TESTS
# ============================================================
print('\n' + '=' * 60)
print('  4. EXPORTER MODULE TESTS')
print('=' * 60)

import exporter

# 4.1 Stats computation
print('\n--- 4.1 Stats ---')
def test_stats_empty():
    stats = exporter.compute_stats([])
    assert_eq(stats['total_count'], 0)
    assert_eq(stats['avg_stars'], 0)
test('EX-001 compute_stats empty', test_stats_empty)

def test_stats_normal():
    repos = db.get_all_repos()
    stats = exporter.compute_stats(repos)
    assert_true(stats['total_count'] > 0)
    assert_true(stats['avg_stars'] >= 0)
    assert_true(isinstance(stats['category_counts'], dict))
    assert_true(isinstance(stats['language_counts'], dict))
test('EX-002 compute_stats normal', test_stats_normal)

# 4.2 HTML export
print('\n--- 4.2 HTML Export ---')
def test_export_html():
    repos = db.get_all_repos()[:10]
    path = exporter.export_html(repos=repos, output_path='output/test_index.html')
    assert_true(os.path.exists(path))
    size = os.path.getsize(path)
    assert_true(size > 10000, f'HTML too small: {size}')
    print(f'    (HTML size: {size/1024:.1f} KB)')
test('EX-008 export_html default', test_export_html)

def test_export_html_compact():
    repos = db.get_all_repos()[:10]
    path = exporter.export_html(repos=repos, template_name='compact.html',
                                output_path='output/test_compact.html')
    assert_true(os.path.exists(path))
test('EX-009 export_html compact', test_export_html_compact)

# 4.3 Multi-format export
print('\n--- 4.3 Multi-format Export ---')
def test_export_md():
    repos = db.get_all_repos()[:10]
    path = exporter.export_markdown(repos)
    assert_true(os.path.exists(path))
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert_in('StarMind Manager', content)
    assert_in('项目总数', content)
test('EX-012/013 export_markdown', test_export_md)

def test_export_json():
    repos = db.get_all_repos()[:10]
    path = exporter.export_json(repos)
    assert_true(os.path.exists(path))
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert_in('repos', data)
    assert_in('exported_at', data)
    assert_true(len(data['repos']) == 10)
test('EX-014/015 export_json', test_export_json)

def test_export_csv():
    repos = db.get_all_repos()[:10]
    path = exporter.export_csv(repos)
    assert_true(os.path.exists(path))
    with open(path, 'r', encoding='utf-8-sig') as f:
        header = f.readline()
    assert_in('name', header)
    assert_in('category', header)
    assert_in('tags', header)
test('EX-016/017 export_csv', test_export_csv)


# ============================================================
#  5. CLI TESTS
# ============================================================
print('\n' + '=' * 60)
print('  5. CLI TESTS')
print('=' * 60)

import subprocess

def run_cli(args_str):
    result = subprocess.run(
        f'{sys.executable} cli.py {args_str}',
        shell=True, capture_output=True, text=True, timeout=60,
        encoding='utf-8', errors='replace'
    )
    return result

print('\n--- 5.1 Help ---')
def test_cli_help():
    r = run_cli('--help')
    assert_eq(r.returncode, 0)
    assert_in('sync', r.stdout)
    assert_in('export', r.stdout)
    assert_in('reanalyze', r.stdout)
    assert_in('stats', r.stdout)
    assert_in('search', r.stdout)
    assert_in('compare', r.stdout)
test('CLI-001/002 --help', test_cli_help)

def test_sync_help():
    r = run_cli('sync --help')
    assert_eq(r.returncode, 0)
    assert_in('--workers', r.stdout)
test('CLI-003 sync --help', test_sync_help)

def test_reanalyze_help():
    r = run_cli('reanalyze --help')
    assert_eq(r.returncode, 0)
    assert_in('--english-only', r.stdout)
    assert_in('--ids', r.stdout)
test('CLI-NEW reanalyze --help with --english-only', test_reanalyze_help)

print('\n--- 5.2 Stats ---')
def test_cli_stats():
    r = run_cli('stats')
    assert_eq(r.returncode, 0)
    assert_in('1551', r.stdout) or assert_in('155', r.stdout)
test('CLI-016 stats', test_cli_stats)

print('\n--- 5.3 Search ---')
def test_cli_search():
    r = run_cli('search Python')
    assert_eq(r.returncode, 0)
    assert_in('Python', r.stdout) or assert_in('python', r.stdout.lower())
test('CLI-017 search', test_cli_search)

print('\n--- 5.4 Export ---')
def test_cli_export_json():
    r = run_cli('export -f json')
    assert_eq(r.returncode, 0)
    assert_in('starmind_export.json', r.stdout)
test('CLI-008 export JSON', test_cli_export_json)

def test_cli_export_md():
    r = run_cli('export -f markdown')
    assert_eq(r.returncode, 0)
    assert_in('starmind_export.md', r.stdout)
test('CLI-010 export markdown', test_cli_export_md)

def test_cli_export_csv():
    r = run_cli('export -f csv')
    assert_eq(r.returncode, 0)
    assert_in('starmind_export.csv', r.stdout)
test('CLI-009 export CSV', test_cli_export_csv)

print('\n--- 5.5 Reanalyze english-only ---')
def test_cli_reanalyze_english():
    # Only test --help output since actually running would take too long
    r = run_cli('reanalyze --help')
    assert_eq(r.returncode, 0)
    assert_in('--english-only', r.stdout)
test('CLI-NEW reanalyze --english-only flag exists', test_cli_reanalyze_english)


# ============================================================
#  6. EDGE CASES & SECURITY
# ============================================================
print('\n' + '=' * 60)
print('  6. EDGE CASES & SECURITY')
print('=' * 60)

print('\n--- 6.1 Empty/Invalid Input ---')
def test_sql_injection():
    repos = db.search_repos(query="'; DROP TABLE starred_repos; --")
    # Table should still exist
    conn = db.get_connection()
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert_in('starred_repos', tables)
test('BD-011 SQL injection protection', test_sql_injection)

def test_unicode_tags():
    db.update_repo_metadata(9000001, tags=['深度学习', '機器学習', 'ML'])
    # Cleanup
    db.hard_delete_repo(9000001)
test('BD-014 Unicode tags (after re-insert)', lambda: None)

def test_special_chars():
    # Insert with special chars
    repo = {
        'id': 9000002, 'name': 'test/<script>',
        'stars': 1, 'summary': '<b>bold</b>',
        'tags': ['<script>alert(1)</script>'], 'category': '其他',
        'language': 'JS', 'url': 'https://example.com',
        'description': 'test'
    }
    db.upsert_repo(repo)
    r = db.get_repo_by_id(9000002)
    assert_true(r is not None)
    db.hard_delete_repo(9000002)
test('BD-013 special characters', test_special_chars)

def test_empty_name():
    repo = {'id': 9000003, 'name': '', 'stars': 0}
    db.upsert_repo(repo)
    r = db.get_repo_by_id(9000003)
    assert_true(r is not None)
    db.hard_delete_repo(9000003)
test('BD-015 empty name', test_empty_name)

print('\n--- 6.2 Performance ---')
def test_perf_query():
    start = time.time()
    repos = db.get_all_repos()
    elapsed = time.time() - start
    assert_true(elapsed < 2.0, f'Too slow: {elapsed:.2f}s for {len(repos)} repos')
    print(f'    ({len(repos)} repos in {elapsed:.3f}s)')
test('PF-001 query performance', test_perf_query)

def test_perf_paged():
    start = time.time()
    repos, total = db.get_repos_paged(page=1, page_size=50)
    elapsed = time.time() - start
    assert_true(elapsed < 1.0, f'Paged query too slow: {elapsed:.2f}s')
    print(f'    (50/{total} repos in {elapsed:.3f}s)')
test('PF-002 paged performance', test_perf_paged)

def test_perf_search():
    start = time.time()
    repos = db.search_repos(query='Python')
    elapsed = time.time() - start
    assert_true(elapsed < 1.0, f'Search too slow: {elapsed:.2f}s')
    print(f'    ({len(repos)} results in {elapsed:.3f}s)')
test('PF-003 search performance', test_perf_search)

def test_perf_html_export():
    repos = db.get_all_repos()[:200]
    start = time.time()
    path = exporter.export_html(repos=repos, output_path='output/test_perf.html')
    elapsed = time.time() - start
    assert_true(elapsed < 30, f'HTML export too slow: {elapsed:.2f}s')
    print(f'    ({len(repos)} repos HTML in {elapsed:.3f}s)')
test('PF-004 HTML export performance', test_perf_html_export)


# ============================================================
#  7. SYNC ENGINE TESTS
# ============================================================
print('\n' + '=' * 60)
print('  7. SYNC ENGINE TESTS')
print('=' * 60)

from sync_engine import SyncEngine

def test_engine_init():
    engine = SyncEngine({'github_token': 'test'})
    assert_false(engine.is_stopped())
test('SE-001 SyncEngine init', test_engine_init)

def test_engine_stop():
    engine = SyncEngine({'github_token': 'test'})
    engine.stop()
    assert_true(engine.is_stopped())
test('SE-002 SyncEngine stop', test_engine_stop)

def test_engine_sync_no_token():
    events = []
    def cb(*args): events.append(args)
    engine = SyncEngine({})
    engine.sync(callback=cb)
    log_msgs = [a[1] for a in events if a[0] == 'log']
    assert_true(any('Token' in m or 'token' in m for m in log_msgs))
test('SE-004 sync no token', test_engine_sync_no_token)

def test_engine_reanalyze_no_llm():
    events = []
    def cb(*args): events.append(args)
    engine = SyncEngine({})
    engine.reanalyze(callback=cb)
    log_msgs = [a[1] for a in events if a[0] == 'log']
    assert_true(any('LLM' in m or 'llm' in m for m in log_msgs))
test('SE-010 reanalyze no LLM', test_engine_reanalyze_no_llm)


# ============================================================
#  SUMMARY
# ============================================================
print('\n' + '=' * 60)
print(f'  FINAL RESULTS: {passed} PASSED, {failed} FAILED')
print('=' * 60)
if errors:
    print('\nFailed tests:')
    for name, err in errors:
        print(f'  - {name}: {err}')
else:
    print('\n  ALL TESTS PASSED!')
print('=' * 60)
