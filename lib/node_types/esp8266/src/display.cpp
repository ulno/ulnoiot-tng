// display.cpp
#include <display.h>

bool Display_Base::init(int w, int h) {
    set_ignore_case(false); // want to use capital letters
    columns = w;
    lines = h;
    ulog("Display with %d columns and %d lines.", columns, lines);
    // create our own textbuffer
    textbuffer = (char *)malloc(lines*columns);
    if(!textbuffer) {
        return false;
        ulog("Could not allocate textbuffer.");
        // TODO: anything which should be destructed now?
    }
    add_subdevice(new Subdevice("",true))->with_receive_cb(
        [&] (const Ustring& payload) {
            Ustring command(payload);
            Ustring subcommand;
            while(true) {
                int pos=command.find("&&");
                if(pos<0) break;
                subcommand.copy(command, pos);
                print(subcommand.as_cstr());
                command.remove(pos+2);
                if(command.starts_with("nl") || command.starts_with("ln")) {
                    command.strip_param();
                    println();
                } else if(command.starts_with("cl")) {
                    command.strip_param();
                    clear();
                    if(command.length()==0) return true; // skip newline at end
                } else if(command.starts_with("go")) {
                    command.strip_param();
                    int x=command.as_int()-1;
                    command.strip_param();
                    int y=command.as_int()-1;
                    command.strip_param();
                    cursor(x,y);
                    if(command.length()==0) return true; // skip newline at end
                } else { // unknown
                    print("&&");
                }
            }
            // Anything coming here should usually just be printed
            println(command.as_cstr());
            return true;
        }
    );
    return true;
}

Display_Base& Display_Base::scroll_up(int nr_lines) {
    // TODO: add cyclic scrolling
    char* from = textbuffer + nr_lines*columns;
    int block_h = lines-nr_lines;
    memmove(textbuffer, from, block_h*columns);
    memset(textbuffer + block_h*columns, ' ', nr_lines*columns);
    return *this;
}

Display_Base& Display_Base::print(const char* str) {
    // TODO: not capped by maxlen -> should not overflow because of Ustring given, but maybe better cap?
    char ch;
    while(*str) {
        ch = *str;
        switch(ch) {
            case '\n':
                cursor_y++;
            case '\r':
                cursor_x=0;
                ch=0;
                break;
            default:
                if(ch<' ') ch = ' ';
                break; 
        }
        if(ch!=0) {
            if(delayed_scroll) {
                scroll_up(1);
                delayed_scroll=false;
            }
            textbuffer[cursor_y * columns + cursor_x] = ch;
            changed = true;
            cursor_x ++;
            if(cursor_x >= columns) {
                cursor_x=0;
                cursor_y++;
            }
        }
        if(cursor_y >= lines) {
            // if(delayed_scroll) {
            //     scroll_up(1);
            // }
            delayed_scroll=true;
            cursor_y = lines-1;
        }
        str++;
    }
    return *this;
}

Display_Base& Display_Base::println() {
    return print("\n");
}

Display_Base& Display_Base::println(const char* str) {
    print(str);
    return println();
}

Display_Base& Display_Base::print(Ustring& ustr) {
    return println(ustr.as_cstr());
}

Display_Base& Display_Base::println(Ustring& ustr) {
    return println(ustr.as_cstr());
}

Display_Base& Display_Base::cursor(int x, int y) {
    cursor_x = limit(x, 0, columns-1);
    cursor_y = limit(y, 0, lines-1);
    delayed_scroll = false;
    return *this;
}

Display_Base& Display_Base::clear() {
    memset(textbuffer, ' ', lines*columns);
    cursor(0,0);
    delayed_scroll = false;
    return *this;
}

bool Display_Base::measure() {
    // TODO: only update when changed?
    unsigned long current = millis();
    if(current - last_frame >= frame_len) {
        if(changed) {
            show(textbuffer);
            changed = false;
        }
        last_frame = current;
    }
    return false;
}


bool Display::init_u8g2() {
    _display->setFont(_font);
    char_height = _display->getMaxCharHeight();
    char_width = _display->getMaxCharWidth();
    set_fps(10); // can be low for these type of displays and just showing text
    if(_display->begin()) {
        if(init( _display->getWidth() / char_width, _display->getHeight() / char_height)) {
            clear();
        }
        return true;
    }
    return false;
}

void Display::show(const char* buffer) {
    char charstr[2]=" ";
    _display->firstPage();
    do {
        for(int y=0; y<lines; y++) {
            for(int x=0; x<columns; x++) {
                charstr[0] = buffer[y * columns + x];
                _display->drawStr(x*char_width, (y+1)*char_height-1, charstr);
            }
        }
    } while ( _display->nextPage() );
}

void Display_HD44780_I2C::init_hd44780_i2c(int w, int h, uint8_t scl, uint8_t sda, int i2c_addr) {
    _display = new LiquidCrystal_I2C(i2c_addr, w, h);
    _display->init(sda, scl);
    if(init(w, h)) {
        clear();
        _display->cursor_off();
        _display->backlight();
    }
    set_fps(2); // can be low for these type of displays and just showing text
}

void Display_HD44780_I2C::show(const char* buffer) {
    char charstr[2]=" ";
    for(int y=0; y<lines; y++) {
        _display->setCursor(0,y);
        for(int x=0; x<columns; x++) {
            charstr[0] = buffer[y * columns + x];
            _display->printstr(charstr);
        }
    }
}
