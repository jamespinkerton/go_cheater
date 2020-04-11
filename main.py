import subprocess, os, argparse
from sgfmill import sgf
from scipy.stats import entropy
import pandas as pd
import GPUtil

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
    b_player = root_node.get("PB")
    w_player = root_node.get("PW")
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
    for node in game.get_main_sequence()[1:]:
        idx += 1
        game_move = node.get_move()
        # Set who the current player and the other player is
        if game_move[0] == 'b':
            cur_player = 'black'
            other_player = 'white'
        else:
            cur_player = 'white'
            other_player = 'black'
        x_coord = let_num_convert[str(game_move[1][0] + 1)]

        cur_move = x_coord + str(game_move[1][1] + 1)
        # The very first move is unique since it requires an extra genmove command...
        # Unfortunately, it's a bit awkward - for example, let's assume black has just played Q16. To determine the "AI probabilty" and then the
        # "human probability", it does the following: for the human, have the human play their move then determine what the AI would want to play as the
        # next white move. From there, invert the probability for the AI's choice to become P(b_win_human). For the AI, have the AI figure out its own
        # black move, then have the AI figure out its own white move and invert the same way to determine P(b_win_ai)
        # This is less than ideal and awkward, but I was unable to find a way to do it more intuitively via Go Text Protocol; open to ideas?
        if idx == 1:
            ai_command_1 = "genmove {}\ngenmove {}".format(cur_player, other_player)
        else:
            ai_command_1 = "genmove {}".format(other_player)
        base_command = "play {} {}".format(cur_player, cur_move)
        ai_command_2 = "genmove {}".format(other_player)
        all_moves.append({'color':cur_player,'current_move':cur_move})
        communicate_string = "\n".join([communicate_string,ai_command_1,"undo","undo",base_command,ai_command_2])
    communicate_string = communicate_string[1:]

    return all_moves, communicate_string

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
    run_string = "{} -g -p {} -w {} {}".format(executable, playouts, weights, final_args)
    print(run_string)
    process = subprocess.Popen(run_string, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    # For whatever reason, the data we want is stored in the error output stream
    (output, err) = process.communicate(bytes(communicate_string, encoding="utf-8"))
    # Decode from bytes, split by newlines
    process.kill()
    raw_lines = err.decode("utf-8",errors="ignore").split("\n")
	
    print("Raw Game Processing Complete...")
    # Run through every line, finding lines that have the key information (i.e. where the AI moved and what the coordinate was)
    computer_moves = []
    for idx, line in enumerate(raw_lines):
        if line.startswith("NN eval=") and line.endswith("\r"):
            raw_move = raw_lines[idx+2].strip().replace("\r","")
            coordinate = raw_move[0:3]
            win_percent = raw_move.split("(V: ")[1].split("%")[0]			
            computer_moves.append({'coordinate':coordinate,'win_percent':win_percent})

    # With the raw extraction complete, now we need to format it prettily and merge it with our human move data
    ai_moves_formatted = []
    y = 0
    for x in range(1,len(computer_moves),4):

        human_percent_b = round((100 - float(computer_moves[x+1]['win_percent'])) * 0.01, 3)
        human_move = all_moves[y]['current_move'].strip()
        ai_move = computer_moves[x-1]['coordinate'].lower().strip()
        if human_move == ai_move:
        	ai_percent_b = human_percent_b
        else:
        	ai_percent_b = round((100 - float(computer_moves[x]['win_percent'])) * 0.01, 3)

        ai_moves_formatted.append({'move_number':y+1,'color':'black','ai_percent':ai_percent_b,
                                  'human_percent': human_percent_b,'ai_move': ai_move,
                                 'human_move':human_move,'entropy':round(entropy([ai_percent_b, human_percent_b]),4)})
        
        if (x + 2) >= len(computer_moves):
        	continue
        try:
            human_percent_w = round((100 - float(computer_moves[x+3]['win_percent'])) * 0.01, 3)
            human_move = all_moves[y+1]['current_move'].strip()
            ai_move = computer_moves[x]['coordinate'].lower().strip()
        except:
            print(computer_moves[x:x+4])
        if human_move == ai_move:
        	ai_percent_w = human_percent_w
        else:
        	ai_percent_w = round((100 - float(computer_moves[x+2]['win_percent'])) * 0.01, 3)
          
        ai_moves_formatted.append({'move_number':y+2,'color':'white','ai_percent': ai_percent_w,
                                  'human_percent': human_percent_w,'ai_move': ai_move,
                                 'human_move':human_move,'entropy':round(entropy([ai_percent_w, human_percent_w]),4)})
        y += 2

    df = pd.DataFrame(ai_moves_formatted)
    # Adding an extra column cause I want to easily see how many moves were equal in the output
    #df['is_same_move'] = df.apply(lambda x: 1 if (x['ai_move'] == x['human_move']) else 0, axis=1)
    proper_order = ["move_number","color","ai_move","human_move","ai_percent","human_percent","entropy"] #,"is_same_move"
    df = df[proper_order]
    return df

if __name__ == "__main__":
    main()
