import subprocess, os, argparse, GPUtil, wexpect
from sgfmill import sgf
import pandas as pd
import progressbar as pb

def main():
    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    optional.add_argument("-p", "--playouts", help="set number of playouts; defaults to 1", default=1)
    optional.add_argument("-w", "--weights", help="indicate where the weights file is; defaults to elfv2 in the local directory", default="elfv2")
    optional.add_argument("-o","--output", help="set the output CSV file", default="output_file.csv")
    optional.add_argument("-e","--executable", help="set the executable Go AI program filename (must have GTP); defaults to leela-zero-0.17-win64/leelaz", default="leelaz")

    required.add_argument("-s", "--sgf", help="indicate where the sgf file is", required=True)
    args = parser.parse_args()

    executable = args.executable
    playouts = args.playouts
    weights = args.weights
    sgf_file = args.sgf
    output_file = args.output

    all_moves, communicate_string = get_moves_communicate_string(sgf_file)

    df = get_csv_output(executable, playouts, weights, communicate_string, all_moves)
    df.to_csv(output_file,index=False)
    print("Success! File outputted to {}".format(output_file))

def get_moves_communicate_string(sgf_file):
    """Returns two values - a list of all human moves in the SGF (all_moves), and a formatted list of those moves for insertion into the Leela CLI (communicate_string)"""
    with open(sgf_file, "rb") as f:
        game = sgf.Sgf_game.from_bytes(f.read())
    winner = game.get_winner()
    board_size = game.get_size()
    root_node = game.get_root()
    try:
        b_player = root_node.get("PB")
    except:
        b_player = "Unknown"
    try:
        w_player = root_node.get("PW")
    except:
        w_player = "Unknown"
    print("The Black player is: {}".format(b_player))
    print("The White player is: {}".format(w_player))
    print("The winner was: {}".format(winner))

    # Basic conversion function from numerical columns to lettered columns
    let_num_convert = {'1':'a','2':'b','3':'c','4':'d','5':'e','6':'f','7':'g','8':'h','9':'j',
                   '10':'k','11':'l','12':'m','13':'n','14':'o','15':'p','16':'q','17':'r',
                   '18':'s','19':'t'}

    communicate_string = ""
    idx = 0
    all_moves = []
    basic_moves = []
    for node in game.get_main_sequence()[1:]:
        idx += 1
        game_move = node.get_move()
        if game_move[1] == None:
            continue
        # Set who the current player and the other player is
        if game_move[0] == 'b':
            cur_player = 'black'
            other_player = 'white'
        else:
            cur_player = 'white'
            other_player = 'black'
        
        x_coord = let_num_convert[str(game_move[1][1] + 1)]
        
        cur_move = x_coord + str(game_move[1][0] + 1)
        #
        computers_move = 'lz-analyze 100 avoid {} pass,resign 1'.format(game_move[0])
        #computers_move = 'genmove {}'.format(game_move[0])
        # 
        humans_move = 'lz-analyze 100 allow {} __ 1 avoid {} pass,resign 1'.format(game_move[0],game_move[0])
        actually_play_move = 'play {} {}'.format(game_move[0],cur_move)
        basic_moves.append(actually_play_move)
        #computers_move = 'lz-analyze {}'.format(game_move[0])
        
        # avoid {} pass,resign 1
        #humans_move = 'lz-genmove_analyze 100 allow {} {} 1'.format(game_move[0],cur_move,game_move[0])
        
        all_moves.append({'color':cur_player,'current_move':cur_move})
        communicate_string = "\n".join([communicate_string,computers_move,humans_move,actually_play_move])
    communicate_string = communicate_string[1:]
    return all_moves, communicate_string

def extract_top_10_moves(before_text):
    top_10_moves = []
    for possible_move_string in before_text:
        v_value = possible_move_string.split("(V: ")[1].split("%")[0]
        n_value = possible_move_string.split("(N: ")[1].split("%")[0]
        lcb_value = possible_move_string.split("(LCB: ")[1].split("%")[0]
        move_coord = possible_move_string.split("->")[0].strip().lower()
        top_10_moves.append({'v_value': float(v_value),'n_value': float(n_value),'lcb_value':float(lcb_value),'move_coord':move_coord})
    return top_10_moves

def get_csv_output(executable, playouts, weights, communicate_string, all_moves):
    """Primary function - first three parameters build the basic setup command, the latter two are used to run the CLI and generate the output CSV"""
    final_args = "--noponder"
    if os.name == 'posix':
        executable = "./leela-zero-0.17/" + executable
        weights = "./leela-zero-0.17/" + weights
    else:
        os.chdir('./leela-zero-0.17')
    if not GPUtil.getGPUs():
        final_args += " --cpu-only"
    run_string = "{} -g -r 0 -d -p {} -w {} {}".format(executable, playouts, weights, final_args)
    print(run_string)
    child = wexpect.spawn('cmd.exe')
    child.expect('>', timeout=120)
    child.sendline(run_string)
    child.expect('Setting max tree', timeout=120)
    starting_commands = ["boardsize 19","clear_board","komi 7.5"]
    for command in starting_commands:
        child.sendline(command)
        child.expect('=', timeout=120)

    communicate_string_list = communicate_string.split("\n")
    with open("command_log.log","w") as my_file:
        my_file.write("\n".join(communicate_string_list))
    y = 0
    all_moves = []
    bar = pb.ProgressBar()
    colors = ['white','black']
    for x in bar(range(0,len(communicate_string_list),3)):
        y += 1
        if y == 181:
            break
        human_move = communicate_string_list[x+2].split(" ")[2]
        child.sendline(communicate_string_list[x])
        child.expect(" max depth", timeout=120)
        before_text = [line.strip() for line in child.before.split("\n") if "->" in line]
        key_move = before_text[0]
        ai_move = key_move.split("->")[0].strip().lower()
        
        ai_v_value = key_move.split("(V: ")[1].split("%")[0]
        ai_n_value = key_move.split("(N: ")[1].split("%")[0]
        ai_lcb_value = key_move.split("(LCB: ")[1].split("%")[0]
        
        move_info = {'move_number':y,'ai_move':ai_move,'ai_v_value':ai_v_value,
                   'ai_n_value':ai_n_value,'ai_lcb_value':ai_lcb_value, 'human_move':human_move, 'color':y%2}
        is_match_found = False
        top_10_moves = extract_top_10_moves(before_text)

        for top_10_move in top_10_moves:
            if top_10_move['move_coord'] == human_move:
                move_info['is_requery_needed'] = 0
                move_info['human_v_value'] = top_10_move['v_value']
                move_info['human_n_value'] = top_10_move['n_value']
                move_info['human_lcb_value'] = top_10_move['lcb_value']
                is_match_found = True
                
        if not is_match_found:
            human_command = communicate_string_list[x+1]
            move_info['is_requery_needed'] = 0
            sorted_top_10 = sorted(top_10_moves, key = lambda i: i['n_value'])
            allowed_moves = human_move
            lowest_n = sorted_top_10[0]['n_value']
            for top_10_move in sorted_top_10[2:]:
                allowed_moves += "," + top_10_move['move_coord']
            human_command = human_command.replace("__",allowed_moves)
            child.sendline(human_command)
            child.expect(" max depth", timeout=120)
            before_text = [line.strip() for line in child.before.split("\n") if "->" in line]
            top_10_moves = extract_top_10_moves(before_text)
            is_found = False
            for top_10_move in top_10_moves:
                if top_10_move['move_coord'] == human_move:
                    move_info['human_v_value'] = top_10_move['v_value']
                    move_info['human_n_value'] = top_10_move['n_value']
                    move_info['human_lcb_value'] = top_10_move['lcb_value']
                    is_found = True
                    break
                    
            if not is_found:
                #print("***************************")
                #print(human_move)
                #print(human_command)
                #print(top_10_moves)
                #print("***************************")
                human_command = human_command.replace(allowed_moves,human_move)
                child.sendline(human_command)
                child.expect(" max depth", timeout=120)
                before_text = [line.strip() for line in child.before.split("\n") if "->" in line]
                top_10_moves = extract_top_10_moves(before_text)
                move_info['human_v_value'] = top_10_moves[0]['v_value']
                move_info['human_n_value'] = lowest_n
                move_info['human_lcb_value'] = top_10_moves[0]['lcb_value']
                move_info['is_requery_needed'] = 1

        all_moves.append(move_info)
        
        child.sendline(communicate_string_list[x+2])
        child.expect('=', timeout=120)
    child.sendline('exit')
    df = pd.DataFrame(all_moves)
    column_order = ["move_number","color","human_move","ai_move","human_v_value","ai_v_value","human_n_value","ai_n_value","human_lcb_value","ai_lcb_value",'is_requery_needed']
    df = df[column_order]
    return df

if __name__ == "__main__":
    main()
