import numpy as np
from scipy.spatial import distance

glossary = {}
glossary_vector = []
path = None
model = None


# name_list and near_vector should be same length, indexed / second match exclude current name from list
def most_sim_names(name_list, near_vectors, cur_vector, cur_name=None, second_match=False, max_num=1):
    name_list_copied = name_list.copy()
    near_vectors_copied = near_vectors.copy()

    if second_match:
        rm_index = name_list.index(cur_name)
        try:
            del name_list_copied[rm_index]
            del near_vectors_copied[rm_index]

        except ValueError:
            # print(f'no {cur_name} in glossary!')
            pass

    distances = distance.cdist(np.array([cur_vector]), np.array(near_vectors_copied), "cosine")[0]

    sim_list = [x for x in enumerate(distances)]
    sim_list.sort(key=lambda x: x[1])

    res_list = []
    for idx, dist in sim_list:
        if len(res_list) >= max_num:
            break
        if len(res_list) == 0 or dist <= 0.5:
            res_list.append([name_list_copied[idx], 1-dist])

    return res_list


def dfs(cur_name, target_name, cur_path, cur_prob, depth_limit=9, jump_limit=1, sim_th=0.35, find_length=None):
    # show possible path
    if find_length and len(cur_path) > find_length:
        path.append([cur_path, cur_prob])
        return

    if depth_limit < 0:
        return

    cur_path = cur_path.copy()

    if cur_name == target_name:
        # return shape : [[path, probability], ... ]
        path.append([cur_path, cur_prob])
        return

    reason_dict = glossary[cur_name].reason

    for reason in reason_dict:
        # prevent cycle
        if reason in cur_path or reason not in glossary:
            continue

        if abs(reason_dict[reason][1]) < sim_th:
            continue

        dfs(reason, target_name, cur_path + [reason], cur_prob + [reason_dict[reason][1]],
            depth_limit - 1, jump_limit, sim_th=sim_th, find_length=find_length)

    # just one hop jump;
    if jump_limit > 0 and len(reason_dict) == 0 and not find_length:
        hopped_name_sim = most_sim_names(list(glossary.keys()), glossary_vector,
                                         model.get_word_vector(cur_name), cur_name, second_match=True)

        hopped_name, hopped_sim = hopped_name_sim[0]

        if hopped_name not in cur_path and abs(hopped_sim) > sim_th:
            dfs(hopped_name, target_name, cur_path + [hopped_name],
                cur_prob + [hopped_sim], depth_limit-1, jump_limit-1, sim_th=sim_th)


# app: find path
def search_path(gs, gsv, model_in, source, dest, depth_limit=9, jump_limit=1, sim_th=0.35):
    global glossary
    global glossary_vector
    global path
    global model

    glossary = gs
    glossary_vector = gsv
    path = []
    model = model_in

    usr_input = source, dest
    sources = [[source, None]]
    destinations = [[dest, None]]

    # if source and dest name is not exist in glossary
    if usr_input[0] not in glossary:
        sources = most_sim_names(list(glossary.keys()), glossary_vector,
                                 model.get_word_vector(source), source, False, 3)
    if usr_input[1] not in glossary:
        destinations = most_sim_names(list(glossary.keys()), glossary_vector,
                                      model.get_word_vector(dest), dest, False, 3)

    '''
    print('source points')
    for i in sources:
        print(i[0], end=', ')
    print('\n')
    print('dest points')
    for i in destinations:
        print(i[0], end=', ')
    print('\n')
    '''

    # source & dest is [['name', similarity], ['name2', similarity2], ...]
    path_index = 0
    for s in sources:
        for d in destinations:
            dfs(s[0], d[0], [s[0]], [], depth_limit=depth_limit, jump_limit=jump_limit, sim_th=sim_th)

            if path_index == len(path):
                continue

            # concat source and dest
            for idx in range(path_index, len(path)):
                if not s[0] == usr_input[0]:
                    path[idx][0].insert(0, usr_input[0])
                    path[idx][1].insert(0, s[1])

            for idx in range(path_index, len(path)):
                if not d[0] == usr_input[1]:
                    path[idx][0].append(usr_input[1])
                    path[idx][1].append(d[1])

            path_index = len(path)

    return path


def hop_vector_space(cur_name, target_name, target_vector, cur_path, cur_prob):
    if cur_name == target_name:
        # return shape : [[path, probability], ... ]
        path.append([cur_path, cur_prob])
        return

    skipped_result = model.filtered_nearest_neighbor(cur_name, 150, 0.55)
    near_names = [i[0] for i in skipped_result]
    near_vectors = [model.get_word_vector(i) for i in near_names]

    next_name_sim = most_sim_names(near_names, near_vectors, target_vector, max_num=1)
    next_name, similarity = next_name_sim[0]

    # print(f'/ {cur_name} -> {next_name}, sim: {similarity}')

    if next_name in cur_path:
        # return shape : [[path, probability], ... ]
        del cur_path[-1]
        del cur_prob[-1]
        path.append([cur_path + [target_name],
                     cur_prob + [distance.cosine(model.get_word_vector(cur_path[-1]), target_vector)]])
        # print('fall into local minimum; duplicated loop! -> terminate!')
        return

    hop_vector_space(next_name, target_name, target_vector,
                     cur_path + [next_name], cur_prob + [similarity])


# app: cross vector space
def across_vector_space(model_in, source, dest):
    global path
    global model

    path = []
    model = model_in

    hop_vector_space(source, dest, model.get_word_vector(dest), [source], [])

    return path


# app: search hidden path
def search_possible_path_with_length(gs, gsv, model_in, source, length=4):
    global glossary
    global glossary_vector
    global path
    global model

    glossary = gs
    glossary_vector = gsv
    path = []
    model = model_in

    sources = [[source, None]]

    # if source name is not exist in glossary
    if source not in glossary:
        sources = most_sim_names(list(glossary.keys()), glossary_vector, model.get_word_vector(source))

    path_index = 0
    for s in sources:
        if sources[0][1] is not None:
            length -= 1
        dfs(s[0], None, [s[0]], [], depth_limit=length, find_length=length)

        if path_index == len(path):
            continue

        # concat source and dest
        for idx in range(path_index, len(path)):
            if not s[0] == source:
                path[idx][0].insert(0, source)
                path[idx][1].insert(0, s[1])

        path_index = len(path)

    return path
